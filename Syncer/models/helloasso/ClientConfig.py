from dataclasses import dataclass, field
from ..Constants import *
from ..app.Config import HelloAssoConfig, HttpClientConfig


@dataclass
class ClientConfig():
    """Configuration for the HelloAssoClient"""
    client_id: str = ""
    client_secret: str = ""

    hello_asso: HelloAssoConfig = field(default_factory=HelloAssoConfig)
    http_client: HttpClientConfig = field(default_factory=HttpClientConfig)
