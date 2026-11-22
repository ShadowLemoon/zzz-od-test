"""开发版（plugins/.dev）与商店版同 ID 并存：按插件的切换选项只加载一份。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.utils.plugin_module_loader import DEV_PLUGIN_DIR_NAME

APP_ID = 'devswitch_demo'

FACTORY_SOURCE = '''
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from . import const


class DemoFactory(ApplicationFactory):
    def __init__(self, ctx):
        ApplicationFactory.__init__(self, const)
        self.ctx = ctx

    def create_application(self, instance_idx, group_id):
        return None
'''


def _write_plugin(plugin_dir: Path, version: str, app_id: str = APP_ID) -> None:
    plugin_dir.mkdir(parents=True)
    (plugin_dir / '__init__.py').write_text('', encoding='utf-8')
    (plugin_dir / 'factory.py').write_text(FACTORY_SOURCE, encoding='utf-8')
    (plugin_dir / 'const.py').write_text(
        f"APP_ID = '{app_id}'\nAPP_NAME = 'demo'\nDEFAULT_GROUP = False\n"
        f"NEED_NOTIFY = False\nVERSION_MARK = '{version}'\n",
        encoding='utf-8',
    )
    (plugin_dir / 'plugin.json').write_text(
        f'{{"version": "{version}"}}', encoding='utf-8'
    )


def _manager(plugins: Path, use_dev_ids: list[str]) -> ApplicationFactoryManager:
    ctx = MagicMock()
    ctx.env_config.is_plugin_use_dev.side_effect = (
        lambda app_id: app_id.casefold() in {i.casefold() for i in use_dev_ids}
    )
    dirs = [(plugins, PluginSource.THIRD_PARTY)]
    dev = plugins / DEV_PLUGIN_DIR_NAME
    if dev.is_dir():
        dirs.append((dev, PluginSource.DEV))
    return ApplicationFactoryManager(ctx, dirs)


@pytest.fixture(autouse=True)
def _clean_modules():
    yield
    for name in [n for n in sys.modules if n == APP_ID or n.startswith(f'{APP_ID}.')]:
        del sys.modules[name]


def test_both_copies_default_loads_market(tmp_path: Path) -> None:
    plugins = tmp_path / 'plugins'
    _write_plugin(plugins / APP_ID, '1.0.0')
    _write_plugin(plugins / DEV_PLUGIN_DIR_NAME / APP_ID, '2.0.0-dev')

    manager = _manager(plugins, [])
    manager.discover_factories(reload_modules=True)

    info = manager.get_plugin_info(APP_ID)
    assert info is not None
    assert info.source == PluginSource.THIRD_PARTY
    assert info.version == '1.0.0'
    assert info.inactive_copy is not None
    assert info.inactive_copy.source == PluginSource.DEV
    assert info.inactive_copy.version == '2.0.0-dev'
    assert manager.scan_failures == []


def test_switch_to_dev_loads_dev_copy_with_same_id(tmp_path: Path) -> None:
    plugins = tmp_path / 'plugins'
    _write_plugin(plugins / APP_ID, '1.0.0')
    _write_plugin(plugins / DEV_PLUGIN_DIR_NAME / APP_ID, '2.0.0-dev')

    manager = _manager(plugins, [APP_ID])
    manager.discover_factories(reload_modules=True)

    info = manager.get_plugin_info(APP_ID)
    assert info is not None
    assert info.app_id == APP_ID
    assert info.source == PluginSource.DEV
    assert info.version == '2.0.0-dev'
    assert info.inactive_copy is not None
    assert info.inactive_copy.source == PluginSource.THIRD_PARTY
    assert manager.scan_failures == []
    assert sys.modules[f'{APP_ID}.const'].VERSION_MARK == '2.0.0-dev'


def test_switch_back_reloads_market_copy(tmp_path: Path) -> None:
    plugins = tmp_path / 'plugins'
    _write_plugin(plugins / APP_ID, '1.0.0')
    _write_plugin(plugins / DEV_PLUGIN_DIR_NAME / APP_ID, '2.0.0-dev')

    manager = _manager(plugins, [APP_ID])
    manager.discover_factories(reload_modules=True)
    assert sys.modules[f'{APP_ID}.const'].VERSION_MARK == '2.0.0-dev'

    manager = _manager(plugins, [])
    manager.discover_factories(reload_modules=True)
    info = manager.get_plugin_info(APP_ID)
    assert info is not None and info.source == PluginSource.THIRD_PARTY
    assert sys.modules[f'{APP_ID}.const'].VERSION_MARK == '1.0.0'


def test_dev_only_loads_regardless_of_switch(tmp_path: Path) -> None:
    plugins = tmp_path / 'plugins'
    _write_plugin(plugins / DEV_PLUGIN_DIR_NAME / APP_ID, '2.0.0-dev')

    manager = _manager(plugins, [])
    manager.discover_factories(reload_modules=True)

    info = manager.get_plugin_info(APP_ID)
    assert info is not None
    assert info.source == PluginSource.DEV
    assert info.inactive_copy is None
    assert info.is_dev_only


def test_dev_dir_name_must_equal_app_id(tmp_path: Path) -> None:
    plugins = tmp_path / 'plugins'
    _write_plugin(plugins / DEV_PLUGIN_DIR_NAME / 'other_dir', '2.0.0-dev')

    manager = _manager(plugins, [])
    manager.discover_factories(reload_modules=True)

    assert manager.get_plugin_info(APP_ID) is None
    assert len(manager.scan_failures) == 1
    for name in [n for n in sys.modules if n == 'other_dir' or n.startswith('other_dir.')]:
        del sys.modules[name]


def test_dev_repo_layout_two_plugins_in_dev_root_not_swallowed(tmp_path: Path) -> None:
    """plugins/.dev 自身不是插件也不是仓库：里面多个插件互不影响。"""
    plugins = tmp_path / 'plugins'
    _write_plugin(plugins / DEV_PLUGIN_DIR_NAME / APP_ID, '2.0.0-dev')
    _write_plugin(plugins / DEV_PLUGIN_DIR_NAME / 'devswitch_two', '1.0', app_id='devswitch_two')

    manager = _manager(plugins, [])
    manager.discover_factories(reload_modules=True)

    assert manager.get_plugin_info(APP_ID) is not None
    assert manager.get_plugin_info('devswitch_two') is not None
    for name in [n for n in sys.modules if n.startswith('devswitch_two')]:
        del sys.modules[name]
