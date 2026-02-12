from integration.plugins.base import EamIntegrationPlugin
from integration.plugins.beam_web_service import BeamWebServicePluginV1
from integration.plugins.excel_bootstrap import ExcelBootstrapPluginV1

_PLUGIN_REGISTRY = {
    ("beam_web_service", "v1"): BeamWebServicePluginV1,
    ("excel_bootstrap", "v1"): ExcelBootstrapPluginV1,
}


def list_plugins() -> list[dict[str, str]]:
    return [
        {"plugin_name": plugin_name, "plugin_version": plugin_version}
        for plugin_name, plugin_version in sorted(_PLUGIN_REGISTRY.keys())
    ]


def get_plugin(plugin_name: str, plugin_version: str) -> EamIntegrationPlugin:
    try:
        plugin_cls = _PLUGIN_REGISTRY[(plugin_name, plugin_version)]
    except KeyError as exc:
        raise ValueError(f"Unsupported plugin: {plugin_name}:{plugin_version}") from exc
    return plugin_cls()
