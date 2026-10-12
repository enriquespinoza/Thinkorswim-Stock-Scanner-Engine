from __future__ import annotations

from schwab.auth import client_from_manual_flow

from src.integrations.schwab.auth import load_schwab_auth_config


def main() -> None:
    config = load_schwab_auth_config(interactive=True)

    print("=" * 88)
    print("SCHWAB MANUAL OAUTH BOOTSTRAP")
    print("=" * 88)
    print(f"Callback URL: {config.callback_url}")
    print(f"Token path: {config.token_path}")
    print()
    print(
        "Follow the schwab-py prompts. After Schwab redirects the browser, "
        "copy the full redirected URL from the browser address bar and paste it here."
    )
    print("Do not share the redirected URL or generated token.")
    print()

    client_from_manual_flow(
        api_key=config.app_key,
        app_secret=config.app_secret,
        callback_url=config.callback_url,
        token_path=str(config.token_path),
        asyncio=False,
        enforce_enums=True,
    )

    if not config.token_path.is_file():
        raise RuntimeError(
            f"Schwab OAuth completed without creating token file: {config.token_path}"
        )

    print()
    print("Schwab authentication bootstrap: OK")
    print(f"Token written -> {config.token_path}")


if __name__ == "__main__":
    main()
