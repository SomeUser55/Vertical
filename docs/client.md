# Описание интерфейса

Сервис осуществляет автоматизированное взаимодействие с клиентами исключительно через протокол 
[HTTP/1.1](https://developer.mozilla.org/ru/docs/Web/HTTP/Overview).  

# URL адреса

Проверка благонадежности: `POST: {host}/api/{version}/reliability/phone`.  

# Криптография

PROD среда располагается внутри защищенного контура: PROXY, 
для прохождения которого необходимо настроить шифрование запросов по 
[ГОСТ-34.10-2012](https://www.altell.ru/legislation/standards/gost-34.10-2012.pdf).  

Для получения сертификатов обратитесь к Вашему менеджеру ОКБ.  

# Токен

Для аутентификации клиентов Сервис использует Bearer Token, 
передаваемый в заголовке HTTP запроса: `Authorization: Bearer TOKEN`.  

Для получения токена обратитесь к Вашему менеджеру ОКБ.  

# Версионирование

Сервис поддерживает [семантическое мажорное версионирование](https://semver.org/lang/ru/).  
Версия сопровождается уникальным идентификатором (v1, v2 и т.д.).   

При выпуске новой версии API предыдущая версия продолжает работать для поддержки старых клиентов.  
При формировании запроса к API всегда необходимо указывать версию.  

> Текущий номер версии: v1.  

# Формат запроса

## Заголовки запроса

Ниже представлены обязательные к отправке HTTP заголовки при обращении к Сервису:  

| Имя           | Значение                        | Значение                             |
|---------------|---------------------------------|--------------------------------------|
| Accept        | application/json; charset=utf-8 | Указывает тип ожидаемого контента    |
| Content-Type  | application/json; charset=utf-8 | Указывает тип передаваемого контента |
| Authorization | Bearer TOKEN                    | Заголовок аутентификации             |

*TOKEN* - персональный токен доступа (строка 64 символа), привязывается к контракту Клиента.  

## Тело запроса

Ниже представлен ожидаемый состав полей запроса:   

| Поле   | Тип    | Обязательное | Значение                                             |
|--------|--------|--------------|------------------------------------------------------|
| number | string | Да           | Мобильный номер в формате 7dddddddddd (только цифры) |

Эти данные необходимо передавать в формате `JSON` и кодировке `UTF-8`.  

Пример:

```json
{
    "number": "78007006050"
}
```

# Формат ответа

## Заголовки ответа

Ниже представлены специальные HTTP заголовки возвращаемые Сервисом:  

| Имя          | Значение | Комментарий                      |
|--------------|----------|----------------------------------|
| X-Request-Id | UUID     | Уникальный идентификатор запроса |

> Настоятельно рекомендуем сохранять уникальный идентификатор запроса для разрешения инцидентов.  

## Коды ответа

Ниже представлен спиосок основных HTTP кодов ответа от нашего API:  

| Код | Название               | Описание                                             |
|-----|------------------------|------------------------------------------------------|
| 200 | OK                     | Запрос успешно обработан                             |
| 400 | Bad Request            | Сервер не разобрал запрос из-за неверного синтаксиса |
| 401 | Unauthorized           | Запрос не прошел аутентификацию или авторизацию      |
| 403 | Forbidden              | Запрос не имеет прав доступа к содержимому           |
| 404 | Not Found              | Запрашиваемый ресурс не найден                       |
| 415 | Unsupported Media Type | Формат данных запроса не поддерживается сервером     |
| 422 | Unprocessable Entity   | Тело запроса содержит ошибки                         |
| 500 | Internal Server Error  | Внутренняя ошибка сервера                            |

## Тело ответа

Сервис возвращает данные в формате `JSON` и в кодировке `UTF-8`.  

Предусмотрены следующий варианты:  

### 200 OK

Код ответа HTTP 200 OK указывает, что запрос выполнен успешно.  

#### Вариант 1

По переданному мобильному номеру не было обращений.  
Об этом свидетельствует поле `period` со значением `null` в разделе `data`.  

```json
{
    "message": "OK",
    "data": {
        "status": false,
        "period": null
    }
}
```

Поле `status` со значением `false` в разделе `data` свидетельствует о неблагонадежности номера.  

#### Вариант 2

По переданному мобильному номеру было совершено одно обращение.  
Об этом свидетельствует поле `period` с одинаковыми значениями дат `registered_at` и `updated_at`.

```json
{
    "message": "OK",
    "data": {
        "status": false,
        "period": {
            "registered_at": "2020.01.01",
            "updated_at": "2020.01.01"
        }
    }
}
```

Поле `status` со значением `false` в разделе `data` свидетельствует о неблагонадежности номера.  

#### Вариант 3

По переданному мобильному номеру было совершено более одного обращения.  
Об этом свидетельствует поле `period` с разными значениями дат `registered_at` и `updated_at`.  

```json
{
    "message": "OK",
    "data": {
        "status": false,
        "period": {
            "registered_at": "2019.05.01",
            "updated_at": "2020.01.01"
        }
    }
}
```

Правило оценки благонадежности мобильного номера НЕ сработало.  
Поле `status` со значением `false` в разделе `data` свидетельствует о неблагонадежности номера.  

#### Вариант 4

По переданному мобильному номеру было совершено более одного обращения.  
Об этом свидетельствует поле `period` с разными значениями дат `registered_at` и `updated_at`.  

```json
{
    "message": "OK",
    "data": {
        "status": true,
        "period": {
            "registered_at": "2019.01.01",
            "updated_at": "2020.01.01"
        }
    }
}
```

Правило оценки благонадежности мобильного номера сработало.  
Поле `status` со значением `true` в разделе `data` свидетельствует о благонадежности номера.  

### 400 BAD REQUEST

Код состояния ответа HTTP 400 Bad Request указывает, что сервер не смог понять 
запрос из-за неверного синтаксиса.  

Клиент не должен повторять этот запрос без изменений.  

Пример:

```json
{
    "message": "Could not parse request body"
}
```

### 401 UNAUTHORIZED

Код ответа на статус ошибки HTTP 401 Unauthorized клиента указывает, что запрос не был применен, 
поскольку ему не хватает действительных учетных данных для целевого ресурса.

Пример (неправильная схема авторизации):

```json
{
    "message": "Invalid authorization scheme"
}
```

Пример (переданный токен невалиден):

```json
{
    "message": "Invalid access token"
}
```

### 415 UNSUPPORTED MEDIA TYPE

Код ответа на ошибку клиента HTTP 415 Unsupported Media Type указывает, что сервер отказывается 
принять запрос, потому что формат содержимого не поддерживается сервером.  

Проблема формата связана со значением заголовка `Content-Type` 
(ожидается только `application/json`):  

```json
{
    "message": "Unsupported media type"
}
```

### 422 UNPROCESSABLE ENTITY

Тело запроса содержит ошибки.

Пример (не указан номер телефона):  

```json
{
    "message": "Input payload validation failed",
    "errors": {
        "number": [
            "Missing data for required field."
        ]
    }
}
```

Пример (Номер телефона не соответствует ожидаемому формату):  

```json
{
    "message": "Input payload validation failed",
    "errors": {
        "number": [
            "Number does't match expected pattern: 7\\d{10}."
        ]
    }
}
```

### 4XX CLIENT ERROR

Все клиентские ошибки в обязательном порядке сопровождаются телом ответа с сообщением, например:  

Ресурс не найден (404):

```json
{
    "message": "Not Found"
}
```

Некорректный метод запроса (405):

```json
{
    "message": "Method Not Allowed"
}
```

### 500 INTERNAL SERVER ERROR

В случае серверной проблемы возвращается исключительно код HTTP 500:

```json
{
    "message": "Internal server error"
}
```

# Ping - Pong

Для проверки подключения к Сервису используйте: `GET: {host}/api/{version}/ping`.  

В случае успеха Сервис вернет код HTTP 200 с телом ответа: 

```json
{
    "data": {},
    "message": "pong"
}
```

В противном случае Сервис вернет код HTTP 500 с телом ответа:

```json
{
    "message": "Internal server error"
}
```
