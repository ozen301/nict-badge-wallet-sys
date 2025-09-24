# Common Workflows

This document summarizes the typical workflows referenced throughout the
project. 

Although most complicated workflows are wrapped up in single functions, it is necessary to recognize the individual steps involved for clarity and future reference. This document serves as a guide to those workflows.

The reader may also refer to the code examples in the [code_examples.ipynb](./code_examples.ipynb) notebook for practical usage of these workflows.

## User Registration
This is wrapped up in the `nictbw.workflows.register_user` function.

0. Instantiate a new `User` object with the information collected from
   the mobile app (e.g. `in_app_id`, nickname). The paymail can be left unset. (This step is not included in the workflow function.)
1. Sign the user up via the blockchain API, supplying the blockchain credentials (username, password, email and optional profile/group information) by using `ChainClient.signup_user`. Captures the generated paymail in the response from the API.
2. Persist the `User` record in the db, including its `paymail` and `on_chain_id` obtained from the step above.
3. Return the registered `User` instance.

## Admin Registration
1. Instantiate a new `Admin` domain object and add it to the active database
   session. 

## User Information Update
1. Modify the relevant `User` object properties in the database session and commit.

## NFT Template Creation
1. Instantiate a new `Template` object describing the NFT metadata.
2. Add the template to the active session and commit.

## NFT Creation and Issuance to a User
This is wrapped up in the `nictbw.workflows.create_and_issue_nft` function.

1. Retrieve the desired `NFTTemplate` via its unique `prefix` or `name`, as well as the target `User` typically via the `in_app_id` or `paymail`. (This is done outside the workflow function. `NFTTemplate.get_by_prefix` or `NFTTemplate.get_by_name` and `User.get_by_in_app_id` or `User.get_by_paymail` can be used here.)
2. Instantiate a new `NFT` object from the template using `NFTTemplate.instantiate_nft`.
3. Mint the NFT on-chain by `NFT.mint_on_chain`, updating minting metadata such as the origin.
4. Persist the NFT to the database and associate it with the recipient `User` using `NFT.issue_dbwise_to`.
5. Return the minted NFT to the caller as needed.

## NFT Synchronization from the Blockchain
The `User.sync_nfts_from_chain` method reconciles the local database with the
blockchain state for a specific user. Use this workflow when NFTs may have been
minted or transferred on-chain without corresponding local records.

1. Ensure the target `User` has an `on_chain_id`. The call will raise a
   `ValueError` if the identifier is missing.
2. Obtain a configured `ChainClient` so the system can call `ChainClient.get_user_nfts` for the user.
3. For each NFT payload returned from the chain, the method:
   - Extracts the embedded metadata (including `metadata.MAP.subTypeData`) and
     maps common aliases (`sharedKey`, `imageUrl`, etc.) to the local schema.
   - Ensures an `NFTTemplate` exists for the NFT prefix, creating a shell
     template populated with the on-chain metadata when necessary.
   - Creates or updates the associated `NFT` row, aligning descriptive fields,
     timestamps, and on-chain identifiers.
   - Creates or refreshes `UserNFTOwnership` rows so the user owns the NFT
     locally, storing the metadata snapshot in `other_meta` and a stable
     `unique_nft_id` derived from the prefix, shared key, or origin.
4. After processing every payload the method reconciles
   `NFTTemplate.minted_count` for all templates touched during the sync so the
   local counts match the on-chain state.

## User Bingo Card Info Update
This is wrapped up in the `nictbw.workflows.update_user_bingo_info` function, which essentially calls the `User.ensure_bingo_cards` and `User.ensure_bingo_cells` method.

However, normally it is not necessary to call these methods directly, as the bingo card and cell info is automatically updated when the user gets a new NFT issued via the `create_and_issue_nft` workflow. This workflow is only needed when the bingo card or cell info gets out of sync for some reason.

1. Query for the `NFTTemplate` entities that have the `triggers_bingo_card` flag set to
   `True` and owned by the user.
2. For each such template, check if the corresponding `BingoCard` is created for the user;
   if not, create it. This ensures that the user has the correct number of bingo cards.
3. Query for the `NFTTemplate` entities owned by the user.
4. For each such template, check if the corresponding `BingoCell` is unlocked for the user;
   if not, unlock it. This ensures that the user has the correct bingo cells unlocked.

## Bingo Card Information Request
This is wrapped up in the `User.bingo_cards_json` and `User.bingo_cards_json_str` function.

1. Query for all `BingoCard` entities requested by the user. We can utilize the relationship and use `[card for card in user.bingo_cards]`.
2. Return an array of cards, each with its associated cell entities info loaded.

---

*Status note:* On-chain registration for users and admins is not yet available
(as of 2025-09-17), so steps referring to these operations remain
conceptual until the integration is complete.
