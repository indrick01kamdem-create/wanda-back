"""
Contrat abstrait pour les providers SMS.

Chaque provider doit implémenter :
- send(phone, code) : envoie le SMS avec le code OTP
- verify(phone, code, stored_hash) : valide le code
  - Twilio Verify : validation côté serveur Twilio
  - AvlyText (et autres) : validation locale via hash
"""

from abc import ABC, abstractmethod


class SMSProvider(ABC):

    @abstractmethod
    async def send(self, phone: str, code: str) -> None:
        """Envoie le code OTP par SMS au numéro donné."""
        ...

    @abstractmethod
    async def verify(self, phone: str, code: str, stored_hash: str) -> bool:
        """
        Vérifie le code OTP.
        - stored_hash : SHA-256 du code stocké en base (utilisé pour validation locale).
        - Retourne True si approuvé, False sinon.
        """
        ...
