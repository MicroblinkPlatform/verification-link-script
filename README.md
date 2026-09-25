# verification-link-script
Script which helps set up verification links for specific region, client credentials &amp; workflowId

# vlink.py — create Microblink verification links

A small command-line script that creates [verification links](https://docs.microblink.com/platform/api/verification-links)
on the Microblink Platform, in the **US East** or **EU** region. You configure your credentials once, then
each run asks for a `userId` and prints the link.

## Requirements

- Python 3.7 or newer. Nothing else: the script uses only the standard library.
- Works on Linux, macOS and Windows. There is no OS-specific code: the same file runs everywhere, using only
  portable standard-library calls. Tested on Windows (Python 3.12) and Linux (Python 3.7 and 3.14).

Check your version:

| OS            | Command              |
|---------------|----------------------|
| Linux / macOS | `python3 --version`  |
| Windows       | `py --version` or `python --version` |

> **macOS (python.org installer):** if you get `CERTIFICATE_VERIFY_FAILED`, run
> `/Applications/Python 3.x/Install Certificates.command` once.

## Commands

The examples below use `python`. On Linux/macOS use `python3`; on Windows `py` also works.

| Command                    | What it does |
|----------------------------|--------------|
| `python vlink.py`          | Asks for a `userId` and creates a link. If nothing is configured yet, runs `init` first. |
| `python vlink.py init`     | Changes the saved settings. Shows each current value; press **Enter** to keep it. |
| `python vlink.py workflow` | Changes **only** the `workflowId`. Region, credentials and expiry stay as they are. |

Any other argument prints the usage text and exits with code `2`.

### Get the script

Clone the repository:

```bash
git clone https://github.com/MicroblinkPlatform/verification-link-script.git
cd verification-link-script
```

Or download it from GitHub (**Code → Download ZIP**), unzip it, and open a terminal in the unzipped `verification-link-script-main` folder.
For example, if you unzipped it into your Downloads folder:

| Shell                  | Command |
|------------------------|---------|
| Linux / macOS terminal | `cd ~/Downloads/verification-link-script-main` |
| Windows PowerShell     | `cd "$HOME\Downloads\verification-link-script-main"` |
| Windows Command Prompt | `cd "%USERPROFILE%\Downloads\verification-link-script-main"` |

If the path has spaces, keep the quotes. You can also run the script from any folder by giving its full
path, e.g. `python "<path to folder>/vlink.py"`.

## 1. Configure (`init`)

```bash
python vlink.py init
```

You are asked for:

| Field          | Notes |
|----------------|-------|
| Region         | `1` = **US East** (default), `2` = **EU**. Press Enter to keep the current region, or US East on a fresh setup. You can also type `us-east` or `eu`. |
| `clientId`     | API client ID from the Microblink Platform, for the selected region. |
| `clientSecret` | API client secret. Typing is hidden. |
| `workflowId`   | ID of the workflow the link starts, e.g. `66d99fa9edc165df54072f8a`. |
| expiry (hours) | **Optional.** How many hours each link stays valid after it is created, e.g. `24`, `48` or `1.5`. Press Enter for the default of **24 hours**. Entering `0` or a negative number also uses 24 hours. The script calculates `expiresOn` from this on every run. |

Example of a first-time setup:

```
Region:
  1) US East  (default)
  2) EU
Select region [Enter = US East]: 2
clientId: my-client-id
clientSecret (hidden):
workflowId: 66d99fa9edc165df54072f8a
expiresOn - hours after each link's creation [Enter = 24]:
Saved.
```

If you run the script before configuring it, `init` starts automatically.

## 2. Create a link

```bash
python vlink.py
```

If the server answers **HTTP 200**, the script prints only the link:

```
userId: customer-42
https://api.us-east.platform.microblink.com/edge/api/v1/verification-link/0266d99fa9edc165df54072f8b
```

Send that link to the end user.

For any other status, it prints an error line with the status and the server's message, then the full
server response, and exits with code `1`:

```
userId: customer-42
Error: HTTP 400 Bad Request - Workflow not found
Server response:
{
  "title": "Bad Request",
  "detail": "Workflow not found"
}
```

## 3. Switch to another workflow (same region)

```bash
python vlink.py workflow
```

```
Region: EU | clientId: my-client-id
workflowId [Enter = keep current]: 66d99fa9edc165df54072f99
Saved.
```

The next `python vlink.py` creates links for the new workflow. To change the region or credentials as well,
use `init`.

## Where settings are saved

Everything is saved in one JSON file in your home folder:

| OS            | Path |
|---------------|------|
| Windows       | `C:\Users\<you>\.microblink-vlink.json` |
| Linux / macOS | `~/.microblink-vlink.json` |

```json
{
  "region": "eu",
  "clientId": "my-client-id",
  "clientSecret": "...",
  "workflowId": "66d99fa9edc165df54072f8a",
  "expiresInHours": 24
}
```

The file stays until you delete it or overwrite it with `init` / `workflow`. It survives
reboots and updates to the script. A file saved by an older version of the script has no `region`, so it uses
US East.

## What the script sends

It sends a `POST` to the selected region's endpoint, authenticated with HTTP Basic auth
(`clientId:clientSecret`):

| Region  | Endpoint |
|---------|----------|
| US East | `https://api.us-east.platform.microblink.com/agent/api/v1/verification-link` |
| EU      | `https://api.eu.platform.microblink.com/agent/api/v1/verification-link` |

```json
{
  "expiresOn": "<creation time + configured hours (default 24)>",
  "workflowId": "<configured workflowId>",
  "consent": {
    "userId": "<entered userId>",
    "givenOn": "<creation time>",
    "isProcessingStoringAllowed": true
  }
}
```

The server returns the link in the `url` field of the response (the public docs call it `address`; the
script accepts either).

To send other consent flags, or extra fields such as `redirectUrl`, `formValues` or `props`, edit the
`body` in `create_link()`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `HTTP 401` / `HTTP 403` | The `clientId` or `clientSecret` is wrong, or belongs to the other region. Run `init` and check the region and credentials. |
| `HTTP 400` / `HTTP 404` | Check the `workflowId` (`python vlink.py workflow`), and that the workflow exists in the selected region. The response body printed with the error has the details. |
| `could not reach the server` / certificate error | Check your connection or proxy. On macOS, see the certificate note above. |
| Something is wrong in the saved settings | Run `python vlink.py init` and retype the values, or delete the settings file and run the script again. |

## Security

The client secret is stored **in plain text** in the settings file. On Linux and macOS the file is readable
only by you (`chmod 600`). On Windows, it relies on your user-profile permissions. Delete the file to remove the
saved credentials.
