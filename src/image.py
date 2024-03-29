from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Union

import numpy as np
import streamlit as st
import tifffile
from PIL import Image

from src.database import query_database


class ImageType(Enum):
    BRIGHT_FIELD = auto()
    MIP = auto()
    HOLOTOMOGRAPHY = auto()


@dataclass
class CellImageMeta:
    image_id: int
    image_name: str | None
    image_type: ImageType | None
    cell_type: str | None
    cell_number: int | None
    cell_id: int | None
    patient_id: int
    patient_name: str | None
    quality: Optional[int]

    @classmethod
    def from_image_id(cls, project_name, image_id) -> CellImageMeta:
        data = query_database(
            f"""SELECT 
                    i.image_id,
                    i.file_name, 
                    i.image_type, 
                    c.cell_type, 
                    c.cell_number, 
                    i.cell_id, 
                    i.patient_id,
                    p.google_drive_parent_name,
                    q.quality
                FROM (
                    SELECT * 
                    from {project_name}_image 
                    WHERE image_id = 1) i
                LEFT JOIN {project_name}_cell c
                ON c.cell_id = i.cell_id
                lEFT JOIN {project_name}_image_quality q
                ON i.image_id = q.image_id
                LEFT JOIN {project_name}_patient p
                ON i.patient_id = p.patient_id"""
        )
        return CellImageMeta(
            image_id,
            data[0].get("file_name"),
            data[0].get("image_type"),
            data[0].get("cell_type"),
            data[0].get("cell_number"),
            data[0].get("cell_id"),
            data[0].get("patient_id"),
            data[0].get("google_drive_parent_name"),
            data[0].get("quality", None),
        )

    @classmethod
    def from_cell_metadata(
        cls,
        project_name: str,
        patient_id: int,
        cell_type: str,
        cell_number: int,
    ) -> list[CellImageMeta]:
        if (cell_type is None) | (cell_number is None):
            return []

        data = query_database(
            f"""SELECT 
                    i.image_id, 
                    i.file_name, 
                    i.image_type, 
                    c.cell_type, 
                    c.cell_number, 
                    c.cell_id, 
                    c.patient_id, 
                    p.google_drive_parent_name, 
                    q.quality
                FROM (SELECT *
                    FROM {project_name}_cell 
                    WHERE cell_type = '{cell_type}'
                    AND cell_number = {cell_number}
                    AND patient_id = {patient_id}) c
                LEFT JOIN {project_name}_image i
                ON i.cell_id = c.cell_id
                LEFT JOIN {project_name}_image_quality q
                ON i.image_id = q.image_id
                LEFT JOIN {project_name}_patient p
                ON i.patient_id = p.patient_id"""
        )
        return [
            CellImageMeta(
                d.get("image_id"),
                d.get("file_name"),
                d.get("image_type"),
                cell_type,
                cell_number,
                d.get("cell_id"),
                patient_id,
                d.get("google_drive_parent_name"),
                d.get("quality", None),
            )  # type: ignore
            for d in data
        ]


class TomocubeImage:
    def __init__(self, image_path: Path):
        self.image_path = image_path

    def process(self):
        image_arr = self.read_image()
        image_arr = self.normalize_img(image_arr)
        return image_arr.astype(np.uint8)

    def read_image(self) -> np.ndarray:
        return tifffile.imread(str(self.image_path))

    @staticmethod
    def normalize_img(img: np.ndarray) -> np.ndarray:
        return (img - np.min(img)) / (np.max(img) - np.min(img)) * 255

    @staticmethod
    def numpy_to_image(img_arr: np.ndarray) -> Image.Image:
        return Image.fromarray(img_arr)

    @staticmethod
    def slice_axis(img_arr: np.ndarray, idx: int, axis: int) -> np.ndarray:
        return img_arr.take(indices=idx, axis=axis)

    @classmethod
    def image_for_streamlit(
        cls, img_arr: np.ndarray, idx: int, axis: int
    ) -> Image.Image:
        return cls.numpy_to_image(
            cls.slice_axis(img_arr, idx, axis).astype(np.uint8)
        )

    @staticmethod
    def render(image, width):
        st.image(image, width=width)


class BFImage(TomocubeImage):
    def read_image(self) -> np.ndarray:
        return np.asarray(Image.open(self.image_path))

    def process(self):
        image_arr = self.read_image()
        return image_arr.astype(np.uint8)


def find_cell_image_by_image_type(
    cell_images: list[CellImageMeta], image_type: ImageType
) -> Union[CellImageMeta, None]:
    results = [
        cell_image
        for cell_image in cell_images
        if cell_image.image_type == image_type.name
    ]
    return results[0] if results else None


def get_images(
    project_name: str, patient_id: int, cell_type: str, cell_number: int
) -> tuple[
    Union[CellImageMeta, None],
    Union[CellImageMeta, None],
    Union[CellImageMeta, None],
]:
    cell_images = CellImageMeta.from_cell_metadata(
        project_name, patient_id, cell_type, cell_number
    )

    bf = find_cell_image_by_image_type(cell_images, ImageType.BRIGHT_FIELD)
    mip = find_cell_image_by_image_type(cell_images, ImageType.MIP)
    ht = find_cell_image_by_image_type(cell_images, ImageType.HOLOTOMOGRAPHY)

    return bf, mip, ht


def download_image(downloader, patient_name, image_name):
    downloader.download(patient_name, image_name)

    if "brightfield" in image_name.lower():
        image_path = Path("image", "bf.tiff")
        st.session_state["bf_image"] = BFImage(image_path).process()

    elif "mip" in image_name.lower():
        image_path = Path("image", "mip.tiff")
        st.session_state["mip_image"] = TomocubeImage(image_path).process()

    elif "tomogram" in image_name.lower():
        image_path = Path("image", "ht.tiff")
        st.session_state["ht_image"] = TomocubeImage(image_path).process()

    else:
        raise ValueError("Invalid image name")
