def get_lightning_name(value: str | None = None) -> str:
    if value is None or str(value).strip() == "":
        value = input("Enter LIGHTNING NAME: ")
    return str(value).strip()
