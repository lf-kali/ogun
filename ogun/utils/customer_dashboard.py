def get_data(data=None):
    data = data or {}

    if "transactions" not in data:
        data["transactions"] = []

    data["transactions"].append({
                "label": "Dispositivos",
                "items": ["Celular", "Notebook"]
            })

    return data

