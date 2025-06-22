import logging.config
import os

file_formatter = {
    "format": "%(asctime)s - %(name)s - %(process)d - %(thread)d - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
}

console_formatter = {
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
}

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def get_logging_config(log_dir: str, log_level: str) -> dict:
    return {
        "version": 1,
        "disable_existing_loggers": False,  
        "formatters": {
            "file": file_formatter,
            "console": console_formatter,
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",  
                "formatter": "console",
                "stream": "ext://sys.stdout",
            },
            "info_rotating_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "file",
                "filename": os.path.join(log_dir, "info.log"),
                "maxBytes": 1024 * 1024 * 10,  # 10 MB
                "backupCount": 5,  # Giữ lại 5 file backup
                "encoding": "utf-8",
            },
            "error_rotating_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "file",
                "filename": os.path.join(log_dir, "error.log"),
                "maxBytes": 1024 * 1024 * 10,  # 10 MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            # Cấu hình cho logger của ứng dụng của bạn
            # __main__ và tên các module khác của bạn sẽ dùng cấu hình này
            "hg_chatbot": {  # <-- THAY TÊN PROJECT CỦA BẠN VÀO ĐÂY
                "level": log_level,
                "handlers": ["console", "info_rotating_file", "error_rotating_file"],
                "propagate": False, # Không truyền log lên logger cha (root)
            },
            # Giảm mức độ "ồn ào" của các thư viện bên thứ ba
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "info_rotating_file"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console", "error_rotating_file"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "WARNING", # Chỉ log các request lỗi, bỏ qua các request 200 OK
                "handlers": ["console", "info_rotating_file"],
                "propagate": False,
            },
            "fastapi": {
                "level": "INFO",
                "handlers": ["console", "info_rotating_file", "error_rotating_file"],
                "propagate": False,
            },
        },
        # Cấu hình cho root logger, bắt tất cả những gì không được định nghĩa ở trên
        "root": {
            "level": "INFO",
            "handlers": ["console", "info_rotating_file", "error_rotating_file"],
        },
    }

def setup_logging():
    log_config = get_logging_config('logs', 'INFO')
    logging.config.dictConfig(log_config)
    logging.info("Logging configured successfully for production environment.")