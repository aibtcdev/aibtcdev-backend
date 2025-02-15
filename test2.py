from backend.factory import backend
from backend.models import ExtensionFilter, XCredsFilter

# i need to get the extension record based on contract_principal

extension = backend.list_extensions(
    filters=ExtensionFilter(
        contract_principal="ST1994Y3P6ZDJX476QFSABEFE5T6YMTJT0T7RSQDW.glitch-onchain-messaging"
    )
)

if extension:
    x_creds = backend.list_x_creds(filters=XCredsFilter(dao_id=extension[0].dao_id))
    print(x_creds)
else:
    print("No extension found")
