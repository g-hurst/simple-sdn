#!/usr/bin/env python3

import argparse
import socket
import threading

def send_udp_packet(hostname, port, iteration):
    message = f"{iteration} Register_Request"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(message.encode(), (hostname, port))
            print(f"UDP packet {iteration} sent successfully to {hostname}:{port}")
    except Exception as e:
        print(f"Failed to send UDP packet {iteration} to {hostname}:{port}. Error: {e}")

def main():

    # Create argument parser
    parser = argparse.ArgumentParser(description="Send UDP packets to a host and port.")
    parser.add_argument("hostname", help="Target hostname")
    parser.add_argument("port", type=int, help="Target port")
    args = parser.parse_args()

    # Send five UDP packets concurrently
    threads = []
    for i in range(6):
        thread = threading.Thread(target=send_udp_packet, args=(args.hostname, args.port, i))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    print("All UDP packets sent.")

if __name__ == "__main__":
    main()

