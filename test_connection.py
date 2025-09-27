#!/usr/bin/env python3
"""Test script to debug HamAlert connection issues."""
import socket
import telnetlib
import time


def test_tcp_connection(host: str, port: int) -> bool:
    """Test basic TCP connectivity."""
    print(f"Testing TCP connection to {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            print("✓ TCP connection successful")
            return True
        else:
            print(f"✗ TCP connection failed with error code: {result}")
            return False
    except Exception as e:
        print(f"✗ TCP connection failed: {e}")
        return False


def test_telnet_handshake(host: str, port: int) -> None:
    """Test telnet connection and initial handshake."""
    print(f"\nTesting telnet handshake with {host}:{port}...")
    try:
        with telnetlib.Telnet(host, port, timeout=30) as tn:
            print("✓ Telnet connection established")

            # Read initial data for 5 seconds
            print("Reading initial server response...")
            for i in range(10):  # Try to read for up to 10 iterations
                try:
                    data = tn.read_very_eager()
                    if data:
                        print(f"Received ({i}): {data}")
                    else:
                        print(f"No data ({i})")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Error reading data ({i}): {e}")
                    break

            print("\nTrying to read until 'login:' prompt...")
            try:
                login_data = tn.read_until(b"login:", timeout=15)
                print(f"Login prompt data: {login_data}")
            except Exception as e:
                print(f"Failed to read login prompt: {e}")

    except Exception as e:
        print(f"✗ Telnet connection failed: {e}")


def main():
    """Run connection tests."""
    host = "hamalert.org"
    port = 7300

    print("HamAlert Connection Test")
    print("=" * 40)

    # Test basic TCP connectivity
    if not test_tcp_connection(host, port):
        print("\nCannot establish basic TCP connection. Check network connectivity.")
        return

    # Test telnet handshake
    test_telnet_handshake(host, port)

    print("\nTest completed.")


if __name__ == "__main__":
    main()