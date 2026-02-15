def check_string(name, value):
    print(f"--- {name} ---")
    print(f"Original: '{value}'")
    print(f"Length: {len(value)}")
    print(f"Hex: {value.encode('utf-8').hex()}")
    print(f"Invisible chars: {[ord(c) for c in value if ord(c) < 32 or ord(c) > 126]}")

INSTANCE_ID = "3EECA6A04BF7413E6BA8B269A10D1A36"
TOKEN = "A85C1AF99D030B9243723276"

check_string("INSTANCE_ID", INSTANCE_ID)
check_string("TOKEN", TOKEN)
