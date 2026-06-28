from garminconnect import Garmin

email = input("Garmin email: ")
password = input("Garmin password: ")

c = Garmin(email, password)
c.login()

try:
    token = c.client.dumps()
    print()
    print("=== YOUR GARMIN TOKEN (copy everything below this line) ===")
    print(token)
except Exception as e:
    print("Could not extract token:", e)
    print("Available attrs on c.client:", [a for a in dir(c.client) if not a.startswith("_")])
