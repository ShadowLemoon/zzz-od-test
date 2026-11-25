"""只有开发版的插件：商店逻辑不匹配它，卸载不删任何目录，详情页可打开目录。"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.application.plugin_info import PluginInfo, PluginSource
from one_dragon_qt.view.plugin import plugin_operation_mixin as mixin_module
from one_dragon_qt.view.plugin.plugin_detail_dialog import (
    ACTION_DELETE_FAILED,
    ACTION_OPEN_DIR,
    ACTION_UNINSTALL,
    ACTION_UNSUBSCRIBE,
)
from one_dragon_qt.view.plugin.plugin_operation_mixin import PluginOperationMixin


class _Page(PluginOperationMixin):

    def __init__(self, plugins: Path) -> None:
        self.plugin_import_service = MagicMock()
        self.plugin_import_service.plugins_dir = plugins
        # 残留的订阅记录：按 APP_ID 能查到
        self.subscription_config = MagicMock()
        self.subscription_config.find_registry_id.return_value = 'demo'
        self.subscription_config.get_record.return_value = {'source': 'market'}
        self._market_snapshot = MagicMock()
        self._import_busy = False
        self.errors: list[str] = []
        self.shown: list = []

    def _show_error(self, title: str, content: str) -> None:
        self.errors.append(content)

    def _show_detail(self, data, action_handler) -> None:
        self.shown.append(data)

    def _as_widget(self):
        return MagicMock()

    def _app_setting_manager(self):
        return None


def _dev_only(plugins: Path) -> PluginInfo:
    plugin_dir = plugins / '.dev' / 'demo'
    plugin_dir.mkdir(parents=True)
    return PluginInfo(
        app_id='demo',
        app_name='demo',
        default_group=False,
        source=PluginSource.DEV,
        plugin_dir=plugin_dir,
        homepage='https://example.invalid/demo',
    )


def test_dev_only_ignores_leftover_subscription(tmp_path: Path) -> None:
    page = _Page(tmp_path)
    info = _dev_only(tmp_path)

    assert page.subscription_registry_id(info) == ''
    assert not page.is_subscribed(info)
    assert page.find_market_entry(info) is None


def test_dev_only_detail_has_open_dir_without_uninstall(tmp_path: Path) -> None:
    page = _Page(tmp_path)
    info = _dev_only(tmp_path)

    page.open_installed_detail(info)

    actions = [action for action, _ in page.shown[0].actions]
    assert ACTION_OPEN_DIR in actions
    assert ACTION_UNINSTALL not in actions
    assert ACTION_UNSUBSCRIBE not in actions


def test_unsubscribe_dev_only_deletes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """入口本身不再拦开发版：即使被直接调用，也定位不到商店版目录，什么都不删。"""
    page = _Page(tmp_path)
    info = _dev_only(tmp_path)
    message_box = MagicMock()
    message_box.return_value.exec.return_value = True
    monkeypatch.setattr(mixin_module, 'MessageBox', message_box)
    page._start_plugin_task = MagicMock()

    page.unsubscribe(info)

    page._start_plugin_task.assert_not_called()
    page.plugin_import_service.delete_plugin.assert_not_called()
    assert len(page.errors) == 1
    assert info.plugin_dir.is_dir()


@pytest.mark.parametrize(
    ('parts', 'expected'),
    [
        (('.dev', 'demo'), [ACTION_OPEN_DIR]),
        (('demo',), [ACTION_DELETE_FAILED, ACTION_OPEN_DIR]),
    ],
)
def test_failed_detail_actions(tmp_path: Path, parts: tuple[str, ...], expected: list[str]) -> None:
    page = _Page(tmp_path)

    page.open_failed_detail(tmp_path.joinpath(*parts), 'boom')

    assert [action for action, _ in page.shown[0].actions] == expected


def test_open_plugin_dir_only_opens_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = _Page(tmp_path)
    opener = MagicMock()
    monkeypatch.setattr(mixin_module, 'QDesktopServices', opener)
    script = tmp_path / 'run.bat'
    script.write_text('', encoding='utf-8')

    page.open_plugin_dir(script)
    page.open_plugin_dir(tmp_path / 'missing')
    opener.openUrl.assert_not_called()
    assert len(page.errors) == 2

    page.open_plugin_dir(tmp_path)
    opener.openUrl.assert_called_once()
