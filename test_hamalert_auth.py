#!/usr/bin/env python3
"""Test HamAlert authentication with real credentials."""
import os
import sys
import telnetlib
import time


def test_hamalert_login():
    """Test complete HamAlert login sequence."""
    host = "hamalert.org"
    port = 7300

    username = os.getenv("USERNAME", "")
    password = os.getenv("PASSWORD", "")

    if not username or not password:
        print("Please set USERNAME and PASSWORD environment variables")
        sys.exit(1)

    print(f"Testing HamAlert login with username: {username}")
    print("=" * 50)

    try:
        with telnetlib.Telnet(host, port, timeout=30) as tn:
            print("✓ Connected to HamAlert")

            # Read login prompt
            login_data = tn.read_until(b"login:", timeout=10)
            print(f"Login prompt: {login_data.decode().strip()}")

            # Send username
            print(f"Sending username: {username}")
            tn.write(username.upper().encode() + b"\n")

            # Read password prompt
            password_data = tn.read_until(b"password:", timeout=10)
            print(f"Password prompt: {password_data.decode().strip()}")

            # Send password
            print("Sending password...")
            tn.write(password.encode() + b"\n")

            # Wait a moment and read response
            print("\nWaiting for authentication response...")
            time.sleep(1)

            # Try to read any immediate response
            immediate = tn.read_very_eager()
            if immediate:
                print(f"Immediate response: {immediate}")

            # Try to read lines for up to 10 seconds
            print("\nReading server responses...")
            for i in range(20):  # 10 seconds total
                try:
                    data = tn.read_until(b"\n", timeout=0.5)
                    if data:
                        line = data.decode().strip()
                        print(f"Line {i}: '{line}'")

                        # Check if we got a command prompt
                        if line.endswith(">"):
                            print("✓ Received command prompt - authentication successful!")

                            # Try to set JSON mode
                            print("Setting JSON mode...")
                            tn.write(b"set/json\n")

                            # Read response
                            response = tn.read_until(b"\n", timeout=5)
                            print(f"JSON mode response: '{response.decode().strip()}'")

                            return True

                        elif any(word in line.lower() for word in ["invalid", "incorrect", "denied", "failed", "error"]):
                            print(f"✗ Authentication failed: {line}")
                            return False

                except Exception as e:
                    if "timed out" not in str(e):
                        print(f"Error reading line {i}: {e}")

            print("✗ No command prompt received - authentication may have failed")
            return False

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


if __name__ == "__main__":
    success = test_hamalert_login()
    sys.exit(0 if success else 1)