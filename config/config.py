import os


class Base:
    """ base config """

    # main
    SECRET_KEY = os.getenv("FLASK_APP_SECRET")
    FLASK_APP_SALT = os.getenv("FLASK_APP_SALT")
    PRODUCT_BASE_URL = os.getenv('PRODUCT_BASE_URL')

    KUBE_SERVICE_PORT = int(os.getenv("KUBE_SERVICE_PORT", "80"))

    # Log level
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")

    # Docker logins (optional)
    SYSTEM_DOCKER_EMAIL = os.getenv("SYSTEM_DOCKER_EMAIL")
    SYSTEM_DOCKER_PASSWORD = os.getenv("SYSTEM_DOCKER_PASSWORD")
    SYSTEM_DOCKER_SERVER = os.getenv("SYSTEM_DOCKER_SERVER", 'docker.io')


class Development(Base):
    """ development config """

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI", "postgresql:///mlops_db")


class Testing(Base):
    """ test environment config """

    TESTING = True
    DEBUG = True
    # use a separate db
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URI") or "postgresql:///mlops_db_test"


class Staging(Base):
    """ Staging config """

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")


class Production(Base):
    """ production config """

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")


app_config = {"development": Development, "testing": Testing,
              "staging": Staging, "production": Production}
