"""
Unit tests for SnipeIT-CLI asset commands and helpers.
"""

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from snipeit import (
    app,
    format_api_error,
    get_name_by_id,
    normalize_row_dict,
    parse_asset_file,
    resolve_asset,
    resolve_id_or_name,
)

runner = CliRunner()


class TestSnipeITHelpers(unittest.TestCase):
    def test_resolve_id_or_name(self):
        items = [
            {"id": 1, "name": "MacBook Pro 16"},
            {"id": 2, "name": "Dell Latitude 7420"},
            {"id": 3, "name": "Ready to Deploy"},
        ]

        # Numeric ID string
        self.assertEqual(resolve_id_or_name("1", items), 1)
        self.assertEqual(resolve_id_or_name(2, items), 2)

        # Exact name match (case-insensitive)
        self.assertEqual(resolve_id_or_name("macbook pro 16", items), 1)
        self.assertEqual(resolve_id_or_name("READY TO DEPLOY", items), 3)

        # Substring / partial match
        self.assertEqual(resolve_id_or_name("Latitude", items), 2)

        # None or empty
        self.assertIsNone(resolve_id_or_name(None, items))
        self.assertIsNone(resolve_id_or_name("", items))
        self.assertIsNone(resolve_id_or_name("Unknown Thing", items))

    def test_get_name_by_id(self):
        items = [{"id": 10, "name": "Headquarters"}, {"id": 20, "name": "Lab A"}]
        self.assertEqual(get_name_by_id(10, items), "Headquarters")
        self.assertEqual(get_name_by_id(99, items), "99")
        self.assertEqual(get_name_by_id(None, items), "-")

    def test_normalize_row_dict(self):
        raw = {
            " Tag ": "ACEP-001 ",
            "MODEL NAME": "MacBook Pro 16",
            "Status Label": "Ready to Deploy",
            "Hostname": "mac-01",
            "PO Number": "PO-12345",
            "Location Name": "Headquarters",
        }
        normalized = normalize_row_dict(raw)
        self.assertEqual(normalized["asset_tag"], "ACEP-001")
        self.assertEqual(normalized["model_id"], "MacBook Pro 16")
        self.assertEqual(normalized["status_id"], "Ready to Deploy")
        self.assertEqual(normalized["name"], "mac-01")
        self.assertEqual(normalized["order_number"], "PO-12345")
        self.assertEqual(normalized["location_id"], "Headquarters")

    def test_parse_asset_file_csv(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("tag,model,status,name\nACEP-1,ModelA,StatusA,host1\n")
            f_path = Path(f.name)

        try:
            rows = parse_asset_file(f_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["asset_tag"], "ACEP-1")
            self.assertEqual(rows[0]["model_id"], "ModelA")
            self.assertEqual(rows[0]["status_id"], "StatusA")
            self.assertEqual(rows[0]["name"], "host1")
        finally:
            f_path.unlink()

    def test_parse_asset_file_json(self):
        data = [
            {"tag": "ACEP-2", "model": "ModelB", "status": "StatusB", "name": "host2"}
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f_path = Path(f.name)

        try:
            rows = parse_asset_file(f_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["asset_tag"], "ACEP-2")
            self.assertEqual(rows[0]["name"], "host2")
        finally:
            f_path.unlink()

    def test_format_api_error(self):
        res_data = {"messages": {"asset_tag": ["Tag already exists."], "model_id": ["Model invalid."]}}
        errs = format_api_error(res_data, 422)
        self.assertIn("asset_tag: Tag already exists.", errs)
        self.assertIn("model_id: Model invalid.", errs)

        res_str = {"messages": "Invalid credentials"}
        self.assertEqual(format_api_error(res_str), ["Invalid credentials"])


class TestSnipeITAssetCommands(unittest.TestCase):
    def test_asset_template(self):
        result = runner.invoke(app, ["asset", "template", "add"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("asset_tag,model,status", result.output)

        result_update = runner.invoke(app, ["asset", "template", "update"])
        self.assertEqual(result_update.exit_code, 0)
        self.assertIn("asset_tag,status,location,notes", result_update.output)

    @patch("snipeit.get_config", return_value=("http://localhost:8000/api/v1", "dummy_token"))
    @patch("requests.post")
    @patch("snipeit.fetch_available_models")
    @patch("snipeit.fetch_available_statuses")
    def test_create_asset_success(self, mock_statuses, mock_models, mock_post, mock_cfg):
        mock_models.return_value = [{"id": 5, "name": "Laptop"}]
        mock_statuses.return_value = [{"id": 10, "name": "Ready to Deploy"}]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "status": "success",
            "payload": {"id": 100, "asset_tag": "TEST-001", "name": "test-box"},
        }
        mock_post.return_value = mock_resp

        result = runner.invoke(app, [
            "asset", "create",
            "--tag", "TEST-001",
            "--model-id", "Laptop",
            "--status-id", "Ready to Deploy",
            "--name", "test-box",
            "-y",
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Created Asset ID: 100", result.output)
        self.assertIn("TEST-001", result.output)

    @patch("snipeit.get_config", return_value=("http://localhost:8000/api/v1", "dummy_token"))
    @patch("snipeit.resolve_asset")
    @patch("requests.patch")
    def test_update_asset_success(self, mock_patch, mock_resolve, mock_cfg):
        mock_resolve.return_value = ({
            "id": 100,
            "asset_tag": "TEST-001",
            "name": "old-name",
            "notes": "old-notes",
        }, [])

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "status": "success",
            "messages": "Asset updated successfully.",
        }
        mock_patch.return_value = mock_resp

        result = runner.invoke(app, [
            "asset", "update", "TEST-001",
            "--name", "new-name",
            "--notes", "updated notes",
            "-y",
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("updated successfully", result.output)

    @patch("snipeit.get_config", return_value=("http://localhost:8000/api/v1", "dummy_token"))
    @patch("snipeit.fetch_available_models")
    @patch("snipeit.fetch_available_statuses")
    @patch("snipeit.fetch_available_locations")
    def test_bulk_add_dry_run(self, mock_locs, mock_statuses, mock_models, mock_cfg):
        mock_models.return_value = [{"id": 1, "name": "ModelX"}]
        mock_statuses.return_value = [{"id": 2, "name": "StatusY"}]
        mock_locs.return_value = []

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("asset_tag,model,status,name\nTAG-101,ModelX,StatusY,pc-01\n")
            f_path = Path(f.name)

        try:
            result = runner.invoke(app, [
                "asset", "bulk-add",
                "--file", str(f_path),
                "--dry-run",
            ])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("[DRY RUN]", result.output)
            self.assertIn("1 valid", result.output)
        finally:
            f_path.unlink()

    @patch("snipeit.get_config", return_value=("http://localhost:8000/api/v1", "dummy_token"))
    @patch("snipeit.resolve_asset")
    @patch("snipeit.fetch_available_statuses")
    def test_bulk_update_dry_run(self, mock_statuses, mock_resolve, mock_cfg):
        mock_statuses.return_value = [{"id": 5, "name": "Archived"}]
        mock_resolve.return_value = ({
            "id": 101,
            "asset_tag": "TAG-101",
            "name": "pc-01",
        }, [])

        result = runner.invoke(app, [
            "asset", "bulk-update", "TAG-101",
            "--status-id", "Archived",
            "--notes", "Retired hardware",
            "--dry-run",
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("[DRY RUN]", result.output)
        self.assertIn("TAG-101", result.output)


if __name__ == "__main__":
    unittest.main()
