import pyotp
from config import ROBINHOOD_MFA_SECRET
from ..utils import logger


# Get MFA code from secret if configured
def get_mfa_code_from_secret():
    if ROBINHOOD_MFA_SECRET:
        mfa_code = pyotp.TOTP(ROBINHOOD_MFA_SECRET).now()
        logger.debug(f"Generated MFA code based on MFA secret: {mfa_code}")
        return mfa_code
    return None
