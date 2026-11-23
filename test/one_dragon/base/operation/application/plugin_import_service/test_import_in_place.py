"""商店更新原地覆盖仓库布局（plugins/<仓库>/<插件>/）的已装插件，不另建平铺副本。"""

from collections.abc import Callable
from pathlib import Path

from one_dragon.base.operation.application.plugin_import_service import (
    PluginImportService,
)

PLUGIN_FILES = {
    "my_plugin/my_plugin_factory.py": "",
    "my_plugin/my_plugin_const.py": 'PLUGIN_VERSION = "2.0.0"',
    "my_plugin/new_file.py": "new",
}


def _make_repo_layout(plugins_dir: Path, with_git: bool) -> Path:
    plugin_dir = plugins_dir / "my_repo" / "my_plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "my_plugin_factory.py").write_text("old", encoding="utf-8")
    (plugin_dir / "my_plugin_const.py").write_text('PLUGIN_VERSION = "1.0.0"', encoding="utf-8")
    if with_git:
        (plugins_dir / "my_repo" / ".git").mkdir()
    return plugin_dir


def test_update_overwrites_repo_layout_in_place(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    plugins_dir = plugin_import_service.plugins_dir
    target = _make_repo_layout(plugins_dir, with_git=False)
    zip_path = tmp_path / "plugin.zip"
    create_zip(zip_path, PLUGIN_FILES)

    result = plugin_import_service.import_plugin(zip_path, overwrite=True, target_dir=target)

    assert result.success
    assert result.plugin_dir == target.resolve()
    assert (target / "new_file.py").read_text(encoding="utf-8") == "new"
    assert (target / "my_plugin_factory.py").read_text(encoding="utf-8") == ""
    assert not (plugins_dir / "my_plugin").exists()


def test_update_in_place_keeps_git_repo_and_backs_up_old_version(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    plugins_dir = plugin_import_service.plugins_dir
    target = _make_repo_layout(plugins_dir, with_git=True)
    zip_path = tmp_path / "plugin.zip"
    create_zip(zip_path, PLUGIN_FILES)

    result = plugin_import_service.import_plugin(zip_path, overwrite=True, target_dir=target)

    assert result.success
    assert (plugins_dir / "my_repo" / ".git").is_dir()
    assert (target / "new_file.py").exists()
    backups = list((plugins_dir / "my_repo").glob(".my_plugin.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "my_plugin_factory.py").read_text(encoding="utf-8") == "old"
    assert not (plugins_dir / "my_plugin").exists()


def test_flat_install_still_writes_plugins_root(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "plugin.zip"
    create_zip(zip_path, PLUGIN_FILES)

    result = plugin_import_service.import_plugin(zip_path, overwrite=True)

    assert result.success
    assert (plugin_import_service.plugins_dir / "my_plugin" / "new_file.py").exists()


def test_in_place_target_rejects_flat_and_hidden_locations(
    plugin_import_service: PluginImportService,
    create_zip: Callable[[Path, dict[str, str]], None],
    tmp_path: Path,
) -> None:
    plugins_dir = plugin_import_service.plugins_dir
    flat = plugins_dir / "my_plugin"
    flat.mkdir(parents=True)
    dev = plugins_dir / ".dev" / "my_plugin"
    dev.mkdir(parents=True)
    zip_path = tmp_path / "plugin.zip"
    create_zip(zip_path, PLUGIN_FILES)

    for bad in (flat, dev, plugins_dir.parent / "elsewhere" / "my_plugin"):
        result = plugin_import_service.import_plugin(zip_path, overwrite=True, target_dir=bad)
        assert not result.success
    assert not (dev / "new_file.py").exists()
    assert not (flat / "new_file.py").exists()
