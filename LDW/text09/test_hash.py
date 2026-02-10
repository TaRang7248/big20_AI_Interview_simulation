from werkzeug.security import check_password_hash

plain_pass = "013579"
try:
    print(f"Testing check_password_hash('{plain_pass}', '{plain_pass}')...")
    result = check_password_hash(plain_pass, plain_pass)
    print(f"Result: {result}")
except Exception as e:
    print(f"Exception: {e}")

print("Done.")
