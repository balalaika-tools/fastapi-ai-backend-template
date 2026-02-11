# Logger — Documentation

* 🔢 Log levels & environment behavior
* ⚙️ Setup combinations (root / external)
* 🧪 Usage examples
* ➕ `extra` usage
* 🚨 Custom `TRACING` level

---

# Logging Levels & Environment Behaviour

The logger behaviour is controlled by:

```
APP_ENVIRONMENT
```

```bash
APP_ENVIRONMENT=dev   # default if unset
APP_ENVIRONMENT=prod
```

---

## 📊 Level Behaviour Matrix

| Environment | Project Logger Level | Root Default | External Default |
| ----------- | -------------------- | ------------ | ---------------- |
| **dev**     | DEBUG                | off          | disable          |
| **prod**    | TRACING (25)         | replace      | propagate        |

---

## 🎯 What This Means

### 🔹 DEV (default)

* Project logs: `DEBUG` and above
* Only `gLogger.*` logs visible
* Third-party logs disabled
* Root untouched

Ideal for clean development debugging.

---

### 🔹 PROD

* Project logs: `TRACING` (25) and above (includes TRACING, WARNING, ERROR, CRITICAL)
* Set `prod_level=logging.WARNING` to exclude TRACING
* All third-party logs propagate to root
* Root replaced with queue pipeline
* Everything JSON formatted

Deterministic, production-grade behaviour.

---

# Root & External Logger Setup Combinations

## 1️⃣ Clean Dev Mode (default)

```python
configure_logging()
```

Result:

* Only project logs
* DEBUG level
* No framework noise

---

## 2️⃣ Full Structured Logging (All Logs JSON)

```python
configure_logging(
    root_handler_mode="replace",
    external_logger_mode="propagate",
)
```

Result:

```
3rd-party → root → queue → JSON formatter
```

✔ All logs structured
✔ No mixed formats
✔ Correlation IDs preserved

---

## 3️⃣ Mixed Mode (Not Recommended)

```python
configure_logging(
    root_handler_mode="add",
    external_logger_mode="keep",
)
```

Possible result:

* Plain-text framework logs
* JSON project logs
* Potential duplicates

Use only if you intentionally want legacy handlers.

---

# Log Levels Explained

Standard levels:

```
DEBUG    = 10
INFO     = 20
TRACING  = 25  (custom — just below WARNING)
WARNING  = 30
ERROR    = 40
CRITICAL = 50
```

---

# 🚨 Custom TRACING Level (25)

Defined between INFO (20) and WARNING (30) — just below WARNING.

Purpose:

* Visible in production by default (since `prod_level = TRACING = 25`)
* Easily toggled off by setting `prod_level=logging.WARNING`
* More important than INFO, less severe than WARNING
* Easily searchable (`.tracing(`)

---

## Example Usage

```python
log = get_logger("gLogger.payment")

log.tracing("Entered payment flow", extra={"order_id": 123})
```

In production:
✔ Visible
✔ JSON formatted
✔ Searchable marker

---

# Basic Usage Examples

## Getting a Logger

```python
log = get_logger("gLogger." + __name__)
```

---

## Standard Logging

```python
log.debug("Debug message")
log.info("User logged in")
log.warning("Low disk space")
log.error("Payment failed")
log.critical("Database unavailable")
```

---

# Using `extra`

Anything passed via `extra` becomes part of the JSON output.

```python
log.info(
    "User login",
    extra={
        "user_id": 42,
        "role": "admin",
        "ip_address": "10.0.0.1"
    }
)
```

JSON output:

```json
{
  "level": "INFO",
  "message": "User login",
  "user_id": 42,
  "role": "admin",
  "ip_address": "10.0.0.1"
}
```

---

## Structured Context Example

```python
log.warning(
    "Payment delayed",
    extra={
        "order_id": 99,
        "amount": 149.99,
        "currency": "EUR",
        "retry_count": 2
    }
)
```

Best practice:

* Use snake_case keys
* Keep values JSON-serializable
* Avoid very large payloads

---

# Correlation ID Example

```python
from your_logging_module import CorrelationCtx

with CorrelationCtx.use("req-abc-123"):
    log.info("Processing request")
```

All logs inside block:

```json
"correlation_id": "req-abc-123"
```

Works with:

* asyncio
* threads
* background tasks

---

# Production-Level Example

```python
configure_logging(
    log_filepath="logs/app.{pid}.log",
    root_handler_mode="replace",
    external_logger_mode="propagate",
    webhook_url="https://hooks.example.com/logs",
    webhook_level=logging.ERROR,
)
```

Behaviour:

* All logs structured
* File rotation enabled
* Errors sent to webhook
* No blocking
* Deterministic formatting

---

# Level Filtering Example

## In DEV

```python
log.debug("visible")
log.info("visible")
log.tracing("visible")
log.warning("visible")
```

All visible.

---

## In PROD (default TRACING)

```python
log.debug("hidden")
log.info("hidden")
log.tracing("visible")   # ✔ included (25 >= 25)
log.warning("visible")
log.error("visible")
```

Only:

```
TRACING
WARNING
ERROR
CRITICAL
```

## In PROD (with prod_level=WARNING)

```python
log.debug("hidden")
log.info("hidden")
log.tracing("hidden")    # ✘ filtered out (25 < 30)
log.warning("visible")
log.error("visible")
```

Only:

```
WARNING
ERROR
CRITICAL
```

---

# When to Use Each Level

| Level    | Value | Use Case                                        |
| -------- | ----- | ------------------------------------------------- |
| DEBUG    | 10    | Detailed internal state                           |
| INFO     | 20    | Normal business events                            |
| TRACING  | 25    | High-importance trace checkpoints (toggle-able)   |
| WARNING  | 30    | Unexpected but recoverable issues                 |
| ERROR    | 40    | Operation failed                                  |
| CRITICAL | 50    | System-level failure                              |

---

# Deterministic Structured Logging Rule

For third-party logs to be JSON formatted:

```
external_logger_mode = "propagate"
AND
root_handler_mode = "replace"
```

Otherwise:

* They may not appear
* Or may appear in mixed format

---

# Summary

This logger provides:

* Environment-aware level control
* Deterministic production behaviour
* Structured JSON output
* Correlation ID support
* Custom TRACING level
* Flexible root/external control
* Fully non-blocking pipeline
