from zrb.helper.typing import Any, Mapping, Optional, Union
from zrb.helper.typecheck import typechecked
from zrb.helper.string.conversion import to_boolean
from zrb.helper.string.jinja import is_probably_jinja
from zrb.helper.render_data import DEFAULT_RENDER_DATA

import os
import jinja2


class AnyExtensionFileSystemLoader(jinja2.FileSystemLoader):
    def get_source(self, environment, template):
        for search_dir in self.searchpath:
            file_path = os.path.join(search_dir, template)
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    contents = file.read()
                return contents, file_path, lambda: False
        raise jinja2.TemplateNotFound(template)


@typechecked
class Renderer():

    def __init__(self):
        self.__input_map: Mapping[str, Any] = {}
        self.__env_map: Mapping[str, str] = {}
        self.__render_data: Optional[Mapping[str, Any]] = None
        self.__rendered_str: Mapping[str, str] = {}

    def get_input_map(self) -> Mapping[str, Any]:
        # This return reference to input map, so input map can be updated
        return self.__input_map

    def _set_input_map(self, key: str, val: Any):
        self.__input_map[key] = val

    def get_env_map(self) -> Mapping[str, str]:
        # This return reference to env map, so env map can be updated
        return self.__env_map

    def _set_env_map(self, key: str, val: str):
        self.__env_map[key] = val

    def render_any(
        self, val: Any, data: Optional[Mapping[str, Any]] = None
    ) -> Any:
        if isinstance(val, str):
            return self.render_str(val, data)
        return val

    def render_float(
        self, val: Union[str, float], data: Optional[Mapping[str, Any]] = None
    ) -> float:
        if isinstance(val, str):
            return float(self.render_str(val, data))
        return val

    def render_int(
        self, val: Union[str, int], data: Optional[Mapping[str, Any]] = None
    ) -> int:
        if isinstance(val, str):
            return int(self.render_str(val, data))
        return val

    def render_bool(
        self, val: Union[str, bool], data: Optional[Mapping[str, Any]] = None
    ) -> bool:
        if isinstance(val, str):
            return to_boolean(self.render_str(val, data))
        return val

    def render_str(
        self, val: str, data: Optional[Mapping[str, Any]] = None
    ) -> str:
        if val in self.__rendered_str:
            return self.__rendered_str[val]
        if not is_probably_jinja(val):
            return val
        template = jinja2.Template(val)
        render_data = self.__get_render_data(additional_data=data)
        try:
            rendered_text = template.render(render_data)
        except Exception:
            raise Exception(f'Fail to render "{val}" with data: {render_data}')
        self.__rendered_str[val] = rendered_text
        return rendered_text

    def render_file(
        self, location: str, data: Optional[Mapping[str, Any]] = None
    ) -> str:
        location_dir = os.path.dirname(location)
        env = jinja2.Environment(
            loader=AnyExtensionFileSystemLoader([location_dir])
        )
        template = env.get_template(location)
        render_data = self.__get_render_data(additional_data=data)
        render_data['TEMPLATE_DIR'] = location_dir
        rendered_text = template.render(render_data)
        return rendered_text

    def __get_render_data(
        self, additional_data: Optional[Mapping[str, Any]] = None
    ) -> Mapping[str, Any]:
        self.__ensure_cached_render_data()
        if additional_data is None:
            return self.__render_data
        return {**self.__render_data, **additional_data}

    def __ensure_cached_render_data(self):
        if self.__render_data is not None:
            return self.__render_data
        render_data = dict(DEFAULT_RENDER_DATA)
        render_data.update({
            'env': self.__env_map,
            'input': self.__input_map,
        })
        self.__render_data = render_data
        return render_data
