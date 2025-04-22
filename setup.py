import subprocess
import os
import sys

def setup_environment():
    print("Setting up environment...")
    
    # Install required packages
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Update farm data
    print("Updating farm data...")
    from update_farm_data import update_farm_data
    update_farm_data('cleaned_output.csv', 'updated_farm_data.csv')
    
    print("Setup completed successfully!")

if __name__ == "__main__":
    setup_environment() 