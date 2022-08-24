import logging
from dataclasses import dataclass

import numpy as np
import streamlit as st
from streamlit_custom_image_labeller import st_custom_image_labeller

from src.cell_selector import render_cell_selector
from src.database import Database, query_database
from src.image import TomocubeImage, download_image, get_images
from src.renderer import LabelProgressRenderer, TitleRenderer
from src.s3 import (
    AWS_KEY,
    AWS_PASSWORD,
    S3Credential,
    S3Downloader,
    get_s3_bucket,
)
from src.session import set_session_state


@dataclass
class Point:
    x: int
    y: int
    z: int


def set_default_point(
    project_name: str, image_id: int, image_size: tuple[int, int, int]
):

    data = query_database(
        f"SELECT image_id, x, y, z FROM {project_name}_image_center WHERE image_id = {image_id}"
    )

    default_point = Point(
        image_size[1] // 2, image_size[2] // 2, image_size[0] // 2
    )

    x = data[0].get("x", default_point.x) if data != () else default_point.x
    y = data[0].get("y", default_point.y) if data != () else default_point.y
    z = data[0].get("z", default_point.z) if data != () else default_point.z

    st.session_state["point"] = Point(x, y, z)


def render_center_labeller(image: np.ndarray):
    col1, col2 = st.columns(2)

    with col1:
        st.header("HT - XY")
        logging.info(f"Render col1 - {st.session_state['point']}")
        output = st_custom_image_labeller(
            TomocubeImage.numpy_to_image(
                TomocubeImage.slice_axis(
                    image, idx=st.session_state["point"].z, axis=0
                )
            ),
            point_color="red",
            point=(
                st.session_state["point"].y,
                st.session_state["point"].x,
            ),  # numpy array axis is not matching with mouse point axis
        )
        st.session_state["point"].y = output[
            "x"
        ]  # numpy array axis is not matching with mouse point axis
        st.session_state["point"].x = output[
            "y"
        ]  # numpy array axis is not matching with mouse point axis

    with col2:
        st.header("HT - YZ")
        logging.info(f"Render col2 - {st.session_state['point']}")
        output2 = st_custom_image_labeller(
            TomocubeImage.numpy_to_image(
                TomocubeImage.slice_axis(
                    image, idx=st.session_state["point"].y, axis=2
                )
            ),
            point_color="red",
            point=(st.session_state["point"].x, st.session_state["point"].z),
        )

        st.session_state["point"].z = output2["y"]


def render_morphology_all_axis(image: np.ndarray) -> None:
    st.subheader("Morphology")

    col1, col2, col3 = st.columns(3)
    with col1:
        _render_each_axis(image, 0)
    with col2:
        _render_each_axis(image, 1)
    with col3:
        _render_each_axis(image, 2)


def _render_each_axis(image: np.ndarray, axis: int) -> None:
    factory = {0: "z", 1: "x", 2: "y"}
    slider_value = st.slider(
        f"{factory[axis]}-axis",
        0,
        image.shape[axis] - 1,
        value=getattr(st.session_state.point, factory[axis]),
    )

    st.image(
        TomocubeImage.image_for_streamlit(image, idx=slider_value, axis=axis),
        use_column_width=True,
        clamp=True,
    )


def save_point(project_name):
    _write_to_database(
        project_name,
        st.session_state["ht_image_meta_center"].image_id,
        st.session_state["point"].x,
        st.session_state["point"].y,
        st.session_state["point"].z,
    )


def _write_to_database(project_name, image_id, x, y, z):
    database = Database()
    sql = f"""INSERT INTO {project_name}_image_center (image_id, x, y, z) 
            VALUES ({image_id}, {x}, {y}, {z}) ON DUPLICATE KEY UPDATE x = {x}, y = {y}, z = {z}"""
    database.execute_sql(sql)
    database.conn.commit()
    database.conn.close()
    del database


def app():
    label_type = "center"

    st.session_state[f"{label_type}_filter_labeled"] = True
    set_session_state(
        f"{label_type}_project_name",
        f"{label_type}_patient_id",
        f"{label_type}_cell_type",
        f"{label_type}_cell_number",
        "ht_image",
        "ht_image_meta_center",
    )

    TitleRenderer("Tomocube Image Quality Labeller").render()

    render_cell_selector(label_type=label_type)  # type: ignore

    project_name = st.session_state[f"{label_type}_project_name"]
    credential = S3Credential(AWS_KEY, AWS_PASSWORD)
    bucket = get_s3_bucket(credential, project_name.replace("_", "-"))
    downloader = S3Downloader(bucket)

    if (st.session_state[f"{label_type}_cell_type"] == "Not Available") | (
        st.session_state[f"{label_type}_cell_number"] == "Not Available"
    ):
        st.write("Not Available images")
        st.write(
            "Please uncheck filter out labeled or check the images really exist."
        )
        return

    _, _, ht_cellimage = get_images(
        st.session_state[f"{label_type}_project_name"],
        st.session_state[f"{label_type}_patient_id"],
        st.session_state[f"{label_type}_cell_type"],
        st.session_state[f"{label_type}_cell_number"],
    )

    if ht_cellimage != st.session_state["ht_image_meta_center"]:
        if ht_cellimage is not None:
            logging.info("Download image")
            download_image(
                downloader,
                ht_cellimage.patient_name,
                ht_cellimage.image_name,
            )
            st.session_state["ht_image_meta_center"] = ht_cellimage
        else:
            st.session_state["ht_image_meta_center"] = None

    if "point" not in st.session_state:
        set_default_point(
            st.session_state["center_project_name"],
            st.session_state["ht_image_meta_center"].image_id,
            st.session_state["ht_image"].shape,
        )

    logging.info(f"point - {st.session_state['point']}")
    logging.info(
        f"ht_image_meta_center - {st.session_state['ht_image_meta_center']}"
    )
    render_center_labeller(st.session_state["ht_image"])

    # st.write(
    #     f"The coordinates of center point: ({st.session_state['point'].x}, {st.session_state['point'].y}, {st.session_state['point'].z})"
    # )

    # st.button(
    #     "Save Point",
    #     on_click=save_point,
    #     args=(st.session_state["center_project_name"],),
    # )

    # if st.checkbox("Show all axis", value=False):
    #     render_morphology_all_axis(st.session_state["ht_image"])

    # with st.sidebar:
    #     LabelProgressRenderer(
    #         st.session_state["center_project_name"], "center"
    #     ).render()
