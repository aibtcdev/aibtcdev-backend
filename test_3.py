import os
from lib.platform import PlatformApi

platform = PlatformApi()

contract_identifier = "ST2QX9NQA3QCM69RQHYG3J9A6VARC3SQXVYM39BMG.gdao-ext004-messaging"
network = "testnet"
dao_record = "1234567890"
current_block_height = 174617

chainhook = platform.create_dao_x_linkage_hook(
                            contract_identifier=contract_identifier,
                            method="send",
                            network=network,
                            name=f"{dao_record}",
                            start_block=current_block_height,
                        )