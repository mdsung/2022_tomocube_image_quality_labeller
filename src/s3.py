# S3 file downloader or iamge load from s3

import os
from dataclasses import dataclass
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv()
AWS_KEY = os.getenv("AWS_KEY")
AWS_PASSWORD = os.getenv("AWS_PASSWORD")


@dataclass
class S3Credential:
    key: str = AWS_KEY  # type:ignore
    password: str = AWS_PASSWORD  # type:ignore

    def __post_init__(self):
        self.key = self.key.strip()
        self.password = self.password.strip()

        assert len(self.key) > 0
        assert len(self.password) > 0


def get_s3_resource(credential: S3Credential):
    return boto3.resource(
        "s3",
        aws_access_key_id=credential.key,
        aws_secret_access_key=credential.password,
    )


def get_s3_bucket(credential: S3Credential, name: str):
    return get_s3_resource(credential).Bucket(name)


class S3Downloader:
    def __init__(self, bucket) -> None:
        self.bucket = bucket

    def download(self, patient_name: str, image_name: str):
        target_file_dict = {
            "brightfield": Path("image", "bf.tiff"),
            "mip": Path("image", "mip.tiff"),
            "tomogram": Path("image", "ht.tiff"),
        }

        for k in target_file_dict.keys():
            if k in image_name.lower():
                target_file = target_file_dict[k]

        self.bucket.download_file(
            f"{patient_name}/{image_name}", str(target_file)
        )


if __name__ == "__main__":
    project_name = "2022_tomocube_igra"
    credential = S3Credential(AWS_KEY, AWS_PASSWORD)
    resource = get_s3_resource(credential)
    bucket = get_s3_bucket(credential, project_name.replace("_", "-"))
    downloader = S3Downloader(bucket)
    image_name = "20220822.121301.809.CD4-001_RI Tomogram.tiff"
    downloader.download("2022-tomocube-igra", "20220822", image_name)
