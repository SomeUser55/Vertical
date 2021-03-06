from http import HTTPStatus
from logging import Logger
from typing import Dict, Optional, TypedDict
from uuid import UUID

from asyncpg.pool import Pool, create_pool
from marshmallow import EXCLUDE, Schema, fields, post_load
from sqlalchemy import Column, ForeignKey, orm
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base

from vertical import hdrs

from .log import LoggerConfig, LoggerSchema
from .protocols import RequestProtocol, ResponseProtocol
from .utils import make_uuid, now

DATETIME_FORMAT = "%Y.%m.%d %H:%M:%S"


Model: DeclarativeMeta = declarative_base()


class Client(Model):
    __tablename__ = "clients"

    id = Column("client_id", pg.UUID, primary_key=True, default=make_uuid)
    name = Column(pg.VARCHAR)
    created_at = Column(pg.TIMESTAMP, default=now)


class Contract(Model):
    __tablename__ = "contracts"

    id = Column("contract_id", pg.UUID, primary_key=True, default=make_uuid)
    client_id = Column(pg.UUID, ForeignKey(Client.id))
    token = Column(pg.VARCHAR)
    created_at = Column(pg.TIMESTAMP, default=now)
    expired_at = Column(pg.TIMESTAMP, default=None)
    revoked_at = Column(pg.TIMESTAMP, default=None)

    client = orm.relationship(Client)

    def is_expired(self) -> bool:
        if self.expired_at is None or self.expired_at > now():
            return False
        return True

    def is_revoked(self) -> bool:
        if self.revoked_at is None or self.revoked_at > now():
            return False
        return True


class Request(Model):
    __tablename__ = "requests"

    id = Column("request_id", pg.UUID, primary_key=True)
    remote = Column(pg.VARCHAR)
    method = Column(pg.VARCHAR)
    path = Column(pg.VARCHAR)
    body = Column(pg.JSONB)
    created_at = Column(pg.TIMESTAMP)


class Response(Model):
    __tablename__ = "responses"

    id = Column("request_id", None, ForeignKey(Request.id), primary_key=True)
    body = Column(pg.JSONB)
    code = Column(pg.SMALLINT)
    created_at = Column(pg.TIMESTAMP)

    request = orm.relationship(Request)


class Identification(Model):
    __tablename__ = "identifications"

    id = Column("identification_id", pg.UUID, primary_key=True)
    request_id = Column(None, ForeignKey(Request.id))
    contract_id = Column(None, ForeignKey(Contract.id))

    request = orm.relationship(Request)
    contract = orm.relationship(Contract)


class AuthException(Exception):
    http_status = HTTPStatus.UNAUTHORIZED

    def render(self) -> str:
        raise NotImplementedError()


class AuthHeaderNotRecognized(AuthException):

    def render(self) -> str:
        return "Authorization header not recognized"


class InvalidAuthScheme(AuthException):

    def render(self) -> str:
        return "Invalid authorization scheme"


class BearerExpected(AuthException):

    def render(self) -> str:
        return "Expected Bearer token type"


class InvalidAccessToken(AuthException):

    def render(self) -> str:
        return "Invalid access token"


class ContractUnavailable(AuthException):

    def __init__(self, contract: Contract):
        self.contract = contract

    def render(self) -> str:
        raise NotImplementedError()


class ContractExpired(ContractUnavailable):

    def render(self) -> str:
        expired_at = self.contract.expired_at.strftime(DATETIME_FORMAT)

        return f"Your contract was expired on {expired_at}"


class ContractRevoked(ContractUnavailable):

    def render(self) -> str:
        revoked_at = self.contract.revoked_at.strftime(DATETIME_FORMAT)

        return f"Your contract was revoked on {revoked_at}"


class AsyncpgPoolConfig(TypedDict, total=False):
    dsn: str
    min_size: str
    max_size: str
    max_queries: str
    max_inactive_connection_lifetime: float
    timeout: float
    command_timeout: float
    statement_cache_size: int
    max_cached_statement_lifetime: float


class AuthServiceConfig(TypedDict):
    pool: AsyncpgPoolConfig
    logger: LoggerConfig


class AuthService:

    __slots__ = (
        "_pool",
        "_logger",
    )

    def __init__(self, pool: Pool, logger: Logger):
        self._pool = pool
        self._logger = logger

    async def setup(self) -> None:
        await self._pool
        self._logger.info("Auth service initialized")

    async def cleanup(self) -> None:
        await self._pool.close()
        self._logger.info("Auth service shutdown")

    async def ping(self) -> bool:
        return await self._pool.fetchval("SELECT TRUE;")

    async def save_request(self, request: RequestProtocol) -> Request:
        query = """
            INSERT INTO requests
                (request_id, remote, method, path, body)
            VALUES
                ($1::UUID, $2::VARCHAR, $3::VARCHAR, $4::VARCHAR, $5::JSONB)
            RETURNING
                requests.request_id AS id
                , requests.remote
                , requests.method
                , requests.path
                , requests.body
            ;
        """

        record = await self._pool.fetchrow(
            query,
            request.identifier,
            request.remote_addr,
            request.method,
            request.path,
            request.body,
        )

        return Request(**record)

    async def save_response(self, response: ResponseProtocol) -> Response:
        query = """
            INSERT INTO responses
                (request_id, code, body)
            VALUES
                ($1::UUID, $2::SMALLINT, $3::JSONB)
            RETURNING
                responses.request_id AS id
                , responses.code
                , responses.body
            ;
        """

        record = await self._pool.fetchrow(
            query,
            response.request.identifier,
            response.code,
            response.body,
        )

        return Response(**record)

    async def get_contract_by_token(self, token: str) -> Optional[Contract]:
        query = """
            SELECT
                contracts.contract_id AS id
                , contracts.client_id
                , contracts.token
                , contracts.created_at
                , contracts.expired_at
                , contracts.revoked_at
            FROM contracts WHERE token = $1::VARCHAR LIMIT 1;
        """

        record = await self._pool.fetchrow(query, token)
        if not record:
            return None
        return Contract(**record)

    async def get_client(self, contract: Contract) -> Client:
        query = """
            SELECT
                clients.client_id AS id
                , clients.name
                , clients.created_at
            FROM
                clients JOIN contracts USING (client_id)
            WHERE
                contracts.contract_id = $1::UUID
            LIMIT 1
            ;
        """

        record = await self._pool.fetchrow(query, contract.id)
        return Client(**record)

    async def identify(self, request_id: UUID, contract_id: UUID):
        query = """
            INSERT INTO identifications
                (request_id, contract_id)
            VALUES
                ($1::UUID, $2::UUID)
            RETURNING
                identifications.identification_id AS id
                , identifications.request_id
                , identifications.contract_id
            ;
        """

        record = await self._pool.fetchrow(query, request_id, contract_id)
        return Identification(**record)

    async def authorize(self, request: RequestProtocol) -> Identification:
        if not request.authorization:
            self._logger.warning("Authorization header not recognized")
            raise AuthHeaderNotRecognized()

        try:
            scheme, token = request.authorization.split()
        except ValueError:
            self._logger.warning("Invalid authorization scheme")
            raise InvalidAuthScheme()

        if scheme != hdrs.BEARER:
            self._logger.warning("Expected Bearer token scheme")
            raise BearerExpected()

        contract = await self.get_contract_by_token(token)

        if not contract:
            self._logger.warning("Contract not found")
            raise InvalidAccessToken()

        self._logger.info(f"Found contract with id {contract.id}")

        client = await self.get_client(contract)

        if contract.is_expired():
            self._logger.warning(f"Contract expired at {contract.expired_at}")
            raise ContractExpired(contract)

        if contract.is_revoked():
            self._logger.warning(f"Contract revoked at {contract.revoked_at}")
            raise ContractRevoked(contract)

        self._logger.info(f"Authorized {client.name} with id {client.id}")

        request_id = UUID(request.identifier)
        return await self.identify(request_id, contract.id)

    @classmethod
    def from_config(cls, config: AuthServiceConfig) -> "AuthService":
        return AuthServiceSchema().load(config)


class AsyncpgPoolSchema(Schema):
    dsn = fields.Str(required=True)
    min_size = fields.Int(missing=0)
    max_size = fields.Int(missing=10)
    max_queries = fields.Int(missing=1000)
    max_inactive_connection_lifetime = fields.Int(missing=3600)
    timeout = fields.Float(missing=10)
    command_timeout = fields.Float(missing=10)
    statement_cache_size = fields.Int(missing=1024)
    max_cached_statement_lifetime = fields.Int(missing=3600)

    class Meta:
        unknown = EXCLUDE

    @post_load
    def make_pool(self, data: Dict, **kwargs) -> Pool:
        return create_pool(**data)


class AuthServiceSchema(Schema):
    pool = fields.Nested(AsyncpgPoolSchema, required=True)
    logger = fields.Nested(LoggerSchema, required=True)

    class Meta:
        unknown = EXCLUDE

    @post_load
    def make_service(self, data: Dict, **kwargs) -> AuthService:
        return AuthService(**data)
