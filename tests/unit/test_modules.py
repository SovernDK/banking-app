from pathlib import Path

from pydantic import SecretStr

from app.config import Settings
from app.modules import DataFiles, build_modules


def _with_bank(settings: Settings, tmp_path: Path, key_path: Path) -> Settings:
    return settings.model_copy(
        update={
            "data_dir": tmp_path,
            "enable_banking_environment": "sandbox",
            "enable_banking_sandbox_id": "app-id",
            "enable_banking_sandbox_key_path": key_path,
        }
    )


def test_without_bank_credentials_there_is_no_bank(settings: Settings, tmp_path: Path) -> None:
    modules = build_modules(settings.model_copy(update={"data_dir": tmp_path}))

    assert modules.bank is None
    assert modules.auto_categoriser is None


def test_every_module_is_built_and_stores_inside_the_data_directory(
    settings: Settings, tmp_path: Path, key_file: Path
) -> None:
    configured = _with_bank(settings, tmp_path, key_file).model_copy(
        update={"ollama_api_key": SecretStr("key")}
    )

    modules = build_modules(configured)

    assert modules.bank is not None
    assert modules.auto_categoriser is not None
    assert modules.files == DataFiles.under(tmp_path)
    modules.category_store.load()
    assert modules.files.categories.exists()


def test_unreadable_bank_key_still_builds_every_module(settings: Settings, tmp_path: Path) -> None:
    configured = _with_bank(settings, tmp_path, tmp_path / "missing.pem")

    assert build_modules(configured).bank is not None
