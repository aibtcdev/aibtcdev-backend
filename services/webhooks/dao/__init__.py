"""DAO webhook service module.

This module provides functionality for handling DAO creation webhooks.
It includes components for parsing and handling webhook payloads related to
creating DAOs, extensions, and tokens.
"""

from services.webhooks.dao.service import DAOService

__all__ = ["DAOService"]
