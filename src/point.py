import logging
from dataclasses import dataclass
from typing import Optional

import streamlit as st

from src.database import query_database


@dataclass
class PointData:
    x: int
    y: int
    z: int


class Point:
    def __init__(
        self,
        project_name: str,
        image_id: int,
        image_size: tuple[int, int, int],
        point: Optional[PointData] = None,
    ):
        self.project_name = project_name
        self.image_id = image_id
        self.image_size = image_size

        self.point = self._get_point_from_database() if point is None else point

    def _get_point_from_database(self) -> PointData | None:
        logging.info(f"{self.project_name}")
        data = query_database(
            f"""SELECT image_id, x, y, z
                FROM {self.project_name}_image_center 
                WHERE image_id = {self.image_id}"""
        )
        logging.info(f"database point={data}")

        try:
            default_point = PointData(
                data[0].get("x"), data[0].get("y"), data[0].get("z")
            )
        except IndexError:
            default_point = self._set_default_point()
            st.session_state["isSaved"] = False
        else:
            st.session_state["isSaved"] = True
        logging.info(default_point)
        return default_point

    def _set_default_point(self) -> PointData:
        return PointData(
            self.image_size[1] // 2,
            self.image_size[2] // 2,
            self.image_size[0] // 2,
        )
