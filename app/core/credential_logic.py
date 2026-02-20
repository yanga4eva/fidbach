import secrets
import string
import logging

logger = logging.getLogger(__name__)

class ProfileManager:
    """
    Manages user credentials and profile information securely.
    """
    def __init__(self):
        self.master_password = None
        self.user_profile = {}
    
    def generate_master_password(self) -> str:
        """
        Generates a high-entropy 16-character password suitable for all automated
        job application account creations.
        """
        if self.master_password:
            return self.master_password
            
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            password = ''.join(secrets.choice(alphabet) for i in range(16))
            if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and sum(c.isdigit() for c in password) >= 3
                and any(c in "!@#$%^&*" for c in password)):
                break
                
        self.master_password = password
        logger.info("New master password generated.")
        return password
        
    def get_master_password(self) -> str:
        """Retrieves the master password, generating one if it doesn't exist."""
        if not self.master_password:
            return self.generate_master_password()
        return self.master_password

    def save_profile(self, profile_data: dict):
        """
        Saves the user profile data needed for job applications.
        """
        required_fields = ['name', 'email', 'phone']
        for field in required_fields:
            if field not in profile_data:
                logger.warning(f"Profile missing required field: {field}")
        
        self.user_profile = profile_data
        logger.info("User profile updated securely in-memory.")
        
    def get_profile(self) -> dict:
        """Returns the current user profile."""
        return self.user_profile

# Global singleton for easy access
profile_manager = ProfileManager()
