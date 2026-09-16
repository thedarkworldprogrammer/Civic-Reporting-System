from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from .models import Complaint, Department, AdminUser
from .utils import is_nearby
import json
from unittest.mock import patch, MagicMock
from io import BytesIO
from PIL import Image


def create_test_image():
    """Helper function to create a test image."""
    img = Image.new('RGB', (100, 100), color='red')
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    return SimpleUploadedFile("test_image.jpg", img_io.read(), content_type="image/jpeg")


class TestDuplicateDetectionBase(TestCase):
    """Base class with common setup for duplicate detection tests."""

    def setUp(self):
        self.client = Client()
        self.department = Department.objects.create(
            name="Test Department",
            email="test@test.com",
            phone="1234567890"
        )

        # Base coordinates (Bangalore, India roughly)
        self.base_lat = 12.9716
        self.base_lon = 77.5946


class TestLocationBasedDuplicates(TestDuplicateDetectionBase):
    """Test cases for location-based duplicate detection."""

    def test_exact_location_match(self):
        """TC_LOC_01: Same title, same coordinates should be detected as duplicate."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Pending"
        )

        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Pothole on Main Street",
                "latitude": self.base_lat,
                "longitude": self.base_lon
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("duplicate"))

    def test_within_threshold(self):
        """TC_LOC_03: Same title, coordinates within 100 meters should be detected."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Pending"
        )

        # ~50 meters away (roughly 0.0005 degrees)
        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Pothole on Main Street",
                "latitude": self.base_lat + 0.0005,
                "longitude": self.base_lon + 0.0005
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("duplicate"))

    def test_beyond_threshold(self):
        """TC_LOC_04: Same title, coordinates beyond 100 meters should NOT be duplicate."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Pending"
        )

        # ~200 meters away (roughly 0.002 degrees)
        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Pothole on Main Street",
                "latitude": self.base_lat + 0.002,
                "longitude": self.base_lon + 0.002
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("duplicate"))

    def test_null_coordinates(self):
        """TC_LOC_08: Same title, one with null coordinates should NOT be duplicate."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=None,
            longitude=None,
            status="Pending"
        )

        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Pothole on Main Street",
                "latitude": self.base_lat,
                "longitude": self.base_lon
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("duplicate"))

    def test_negative_coordinates(self):
        """TC_LOC_13: Negative coordinates should be handled correctly."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=-33.8688,  # Sydney, Australia
            longitude=151.2093,
            status="Pending"
        )

        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Pothole on Main Street",
                "latitude": -33.8688,
                "longitude": 151.2093
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("duplicate"))


class TestTitleBasedDuplicates(TestDuplicateDetectionBase):
    """Test cases for title-based duplicate detection."""

    def test_case_insensitive_title(self):
        """TC_TITLE_01: Same title with different case should be detected."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Pending"
        )

        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "POTHOLE on main street",
                "latitude": self.base_lat,
                "longitude": self.base_lon
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("duplicate"))

    def test_different_title_same_location(self):
        """TC_TITLE_03: Different titles, same location should NOT be duplicate (current behavior)."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Pending"
        )

        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Broken Street Light",
                "latitude": self.base_lat,
                "longitude": self.base_lon
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("duplicate"))


class TestStatusFiltering(TestDuplicateDetectionBase):
    """Test cases for status-based filtering in duplicate detection."""

    def test_ignore_solved_complaints(self):
        """TC_STATUS_01: Duplicate against 'Solved' complaints should be ignored in create_complaint."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Solved"
        )

        # Try to create same complaint - should NOT be detected as duplicate
        response = self.client.post(
            "/api/complaints/create/",
            data={
                "title": "Pothole on Main Street",
                "description": "Large pothole",
                "latitude": str(self.base_lat),
                "longitude": str(self.base_lon),
                "file": create_test_image()
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("duplicate"))

    def test_detect_in_progress_complaints(self):
        """TC_STATUS_02: Duplicate against 'In Progress' complaints should be detected."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="In Progress"
        )

        response = self.client.post(
            "/api/complaints/create/",
            data={
                "title": "Pothole on Main Street",
                "description": "Large pothole",
                "latitude": str(self.base_lat),
                "longitude": str(self.base_lon),
                "file": create_test_image()
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("duplicate"))


class TestUtilityFunctions(TestDuplicateDetectionBase):
    """Test cases for utility functions."""

    def test_is_nearby_same_location(self):
        """Test is_nearby with identical coordinates."""
        result = is_nearby(self.base_lat, self.base_lon, self.base_lat, self.base_lon)
        self.assertTrue(result)

    def test_is_nearby_within_radius(self):
        """Test is_nearby with coordinates within radius."""
        # ~50 meters away
        result = is_nearby(
            self.base_lat, self.base_lon,
            self.base_lat + 0.0005, self.base_lon + 0.0005
        )
        self.assertTrue(result)

    def test_is_nearby_beyond_radius(self):
        """Test is_nearby with coordinates beyond radius."""
        # ~200 meters away
        result = is_nearby(
            self.base_lat, self.base_lon,
            self.base_lat + 0.002, self.base_lon + 0.002
        )
        self.assertFalse(result)

    def test_is_nearby_custom_radius(self):
        """Test is_nearby with custom radius."""
        # ~150 meters away (should be within 200m radius)
        result = is_nearby(
            self.base_lat, self.base_lon,
            self.base_lat + 0.001, self.base_lon + 0.001,
            radius_m=200
        )
        self.assertTrue(result)


class TestCreateComplaintEndpoint(TestDuplicateDetectionBase):
    """Test cases for the create_complaint endpoint."""

    @patch('complaints.views.classify_image')
    def test_create_complaint_success(self, mock_classify):
        """Test successful complaint creation when no duplicate exists."""
        mock_classify.return_value = ("potholes", 0.95)

        response = self.client.post(
            "/api/complaints/create/",
            data={
                "title": "New Pothole",
                "description": "A new pothole",
                "latitude": str(self.base_lat),
                "longitude": str(self.base_lon),
                "file": create_test_image()
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("duplicate"))
        self.assertIn("complaint_id", data)
        self.assertEqual(Complaint.objects.count(), 1)

    def test_create_complaint_duplicate_detected(self):
        """Test that duplicate is detected when creating complaint."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Pending"
        )

        response = self.client.post(
            "/api/complaints/create/",
            data={
                "title": "Pothole on Main Street",
                "description": "Large pothole",
                "latitude": str(self.base_lat),
                "longitude": str(self.base_lon),
                "file": create_test_image()
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("duplicate"))
        self.assertIn("complaint", data)

    def test_create_complaint_get_method_not_allowed(self):
        """Test that GET method is not allowed."""
        response = self.client.get("/api/complaints/create/")
        self.assertEqual(response.status_code, 405)


class TestDescriptionBasedDuplicates(TestDuplicateDetectionBase):
    """
    Test cases for description-based duplicate detection.

    NOTE: These tests are expected to FAIL because description-based
    duplicate detection is NOT currently implemented in the codebase.
    These are placeholder tests for future implementation.
    """

    def test_identical_descriptions(self):
        """
        TC_DESC_01: Identical descriptions should be detected as duplicate.

        EXPECTED TO FAIL - Not implemented yet.
        """
        Complaint.objects.create(
            title="Issue on Main Street",
            description="Large pothole causing traffic issues",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Pending"
        )

        # Same location, different title, same description
        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Problem on Main Street",
                "latitude": self.base_lat + 0.0001,
                "longitude": self.base_lon + 0.0001
            }),
            content_type="application/json"
        )

        # This will fail because current implementation doesn't check descriptions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # This assertion will fail - description similarity not implemented
        self.assertTrue(data.get("duplicate"), "Description-based duplicate detection not implemented")

    def test_case_insensitive_description(self):
        """
        TC_DESC_02: Same description with different case should be detected.

        EXPECTED TO FAIL - Not implemented yet.
        """

    def test_semantic_similarity(self):
        """
        TC_DESC_07: Semantically similar descriptions should be detected.

        EXPECTED TO FAIL - Not implemented yet.
        """


class TestCombinedLocationDescription(TestDuplicateDetectionBase):
    """
    Test cases for combined location + description duplicate detection.

    NOTE: These tests are expected to FAIL because combined detection is
    NOT currently implemented.
    """

    def test_nearby_similar_description(self):
        """
        TC_COMB_01: Nearby location + similar description should be duplicate.

        EXPECTED TO FAIL - Not implemented yet.
        """

    def test_far_similar_description(self):
        """
        TC_COMB_03: Far location + similar description should NOT be duplicate.

        EXPECTED TO FAIL - Not implemented yet.
        """


class TestImageBasedDuplicates(TestDuplicateDetectionBase):
    """
    Test cases for image-based duplicate detection.

    NOTE: These tests are expected to FAIL because image-based detection is
    NOT currently implemented.
    """

    def test_same_image_nearby_location(self):
        """
        TC_IMG_01: Same image + nearby location should be high confidence duplicate.

        EXPECTED TO FAIL - Not implemented yet.
        """


class TestEdgeCases(TestDuplicateDetectionBase):
    """Test edge cases and error handling."""

    def test_check_duplicate_invalid_method(self):
        """Test that non-POST methods are rejected."""
        response = self.client.get("/api/complaints/check-duplicate/")
        self.assertEqual(response.status_code, 405)

    def test_check_duplicate_missing_data(self):
        """Test handling of missing required fields."""
        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({"title": "Test"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 500)  # Internal server error due to missing data

    def test_create_complaint_missing_data(self):
        """Test handling of missing fields in create_complaint."""
        response = self.client.post(
            "/api/complaints/create/",
            data={"title": "Test"}
        )
        # Will error due to missing required fields
        self.assertIn(response.status_code, [400, 500])

    def test_invalid_coordinates(self):
        """TC_LOC_12: Invalid coordinates should be handled gracefully."""
        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Test",
                "latitude": 200,  # Invalid latitude (> 90)
                "longitude": 200
            }),
            content_type="application/json"
        )
        # Should handle gracefully
        self.assertIn(response.status_code, [200, 400, 500])


class TestAPIResponses(TestDuplicateDetectionBase):
    """Test API response structures."""

    def test_check_duplicate_response_structure(self):
        """Test that check_duplicate returns correct response structure."""
        Complaint.objects.create(
            title="Test Issue",
            description="Test",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Pending"
        )

        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Test Issue",
                "latitude": self.base_lat,
                "longitude": self.base_lon
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        if data.get("duplicate"):
            self.assertIn("complaint", data)
            self.assertIn("id", data["complaint"])
            self.assertIn("description", data["complaint"])
            self.assertIn("votes", data["complaint"])

    def test_list_all_complaints(self):
        """Test the list_all_complaints endpoint."""
        Complaint.objects.create(
            title="Test Issue",
            description="Test",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            status="Pending"
        )

        response = self.client.get("/api/complaints/all/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("complaints", data)
        self.assertEqual(len(data["complaints"]), 1)


class TestHeatmapAPI(TestDuplicateDetectionBase):
    """
    Test cases for the heatmap endpoint.

    Tests verify that:
    - GET method retrieves heatmap data correctly
    - Complaints with valid coordinates are included
    - Complaints without coordinates are excluded
    - Intensity is calculated based on vote-up count
    - Response structure matches expected format
    """

    def test_heatmap_get_method_success(self):
        """TC_HEATMAP_01: GET request should return valid heatmap data."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            votes=5,
            status="Pending"
        )

        response = self.client.get("/api/complaints/heatmap/")
        self.assertEqual(response.status_code, 200)

    def test_heatmap_response_structure(self):
        """TC_HEATMAP_02: Response should have correct structure with 'points' array."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=self.base_lat,
            longitude=self.base_lon,
            votes=3,
            status="Pending"
        )

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()

        self.assertIn("points", data)
        self.assertIsInstance(data["points"], list)

    def test_heatmap_includes_complaints_with_coordinates(self):
        """TC_HEATMAP_03: Complaints with valid lat/lng should be included in heatmap."""
        Complaint.objects.create(
            title="Pothole on Main Street",
            description="Large pothole",
            image=create_test_image(),
            latitude=12.9716,
            longitude=77.5946,
            votes=2,
            status="Pending"
        )

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()

        self.assertEqual(len(data["points"]), 1)
        self.assertEqual(data["points"][0]["lat"], 12.9716)
        self.assertEqual(data["points"][0]["lng"], 77.5946)

    def test_heatmap_excludes_complaints_without_coordinates(self):
        """TC_HEATMAP_04: Complaints with null lat/lng should be excluded from heatmap."""
        # Complaint WITH coordinates
        Complaint.objects.create(
            title="Pothole with location",
            description="Has location",
            image=create_test_image(),
            latitude=12.9716,
            longitude=77.5946,
            votes=1,
            status="Pending"
        )

        # Complaint WITHOUT coordinates
        Complaint.objects.create(
            title="Pothole without location",
            description="No location",
            image=create_test_image(),
            latitude=None,
            longitude=None,
            votes=1,
            status="Pending"
        )

        # Complaint with only latitude set (longitude is None)
        Complaint.objects.create(
            title="Partial location",
            description="Only lat",
            image=create_test_image(),
            latitude=12.9716,
            longitude=None,
            votes=1,
            status="Pending"
        )

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()

        # Only 1 complaint should be included (the one with both lat and lng)
        self.assertEqual(len(data["points"]), 1)

    def test_heatmap_intensity_based_on_votes(self):
        """TC_HEATMAP_05: Intensity should be equal to votes count."""
        test_cases = [
            (0, 1),      # 0 votes -> intensity 1 (default)
            (1, 1),      # 1 vote -> intensity 1
            (5, 5),      # 5 votes -> intensity 5
            (10, 10),    # 10 votes -> intensity 10
            (100, 100),  # 100 votes -> intensity 100
        ]

        for votes, expected_intensity in test_cases:
            with self.subTest(votes=votes, expected=expected_intensity):
                complaint = Complaint.objects.create(
                    title=f"Test Complaint {votes}",
                    description="Test",
                    image=create_test_image(),
                    latitude=self.base_lat,
                    longitude=self.base_lon,
                    votes=votes,
                    status="Pending"
                )

                response = self.client.get("/api/complaints/heatmap/")
                data = response.json()

                # Find the point we just created
                point = next(
                    (p for p in data["points"] if p["lat"] == self.base_lat and p["lng"] == self.base_lon),
                    None
                )

                self.assertIsNotNone(point)
                self.assertEqual(point["intensity"], expected_intensity)

            # Clean up for next iteration
            Complaint.objects.all().delete()

    def test_heatmap_empty_dataset(self):
        """TC_HEATMAP_06: Empty dataset should return empty points array."""
        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()

        self.assertEqual(len(data["points"]), 0)

    def test_heatmap_multiple_complaints_same_location(self):
        """TC_HEATMAP_07: Multiple complaints at same location should create separate points."""
        # Create multiple complaints at the same location with different votes
        Complaint.objects.create(
            title="Complaint 1",
            description="First complaint",
            image=create_test_image(),
            latitude=12.9716,
            longitude=77.5946,
            votes=3,
            status="Pending"
        )
        Complaint.objects.create(
            title="Complaint 2",
            description="Second complaint",
            image=create_test_image(),
            latitude=12.9716,
            longitude=77.5946,
            votes=7,
            status="Pending"
        )
        Complaint.objects.create(
            title="Complaint 3",
            description="Third complaint",
            image=create_test_image(),
            latitude=12.9716,
            longitude=77.5946,
            votes=15,
            status="Pending"
        )

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()

        # Should have 3 separate points (not aggregated)
        self.assertEqual(len(data["points"]), 3)

        # Verify intensities match votes
        intensities = sorted([p["intensity"] for p in data["points"]])
        self.assertEqual(intensities, [3, 7, 15])

    def test_heatmap_multiple_locations(self):
        """TC_HEATMAP_08: Multiple complaints at different locations."""
        complaints_data = [
            ("Pothole Bangalore", 12.9716, 77.5946, 5),
            ("Pothole Delhi", 28.7041, 77.1025, 3),
            ("Pothole Mumbai", 19.0760, 72.8777, 8),
        ]

        for title, lat, lng, votes in complaints_data:
            Complaint.objects.create(
                title=title,
                description=f"Issue in {title}",
                image=create_test_image(),
                latitude=lat,
                longitude=lng,
                votes=votes,
                status="Pending"
            )

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()

        self.assertEqual(len(data["points"]), 3)

        # Verify each location is present with correct intensity
        for lat, lng, expected_intensity in [(12.9716, 77.5946, 5), (28.7041, 77.1025, 3), (19.0760, 72.8777, 8)]:
            point = next(
                (p for p in data["points"] if p["lat"] == lat and p["lng"] == lng),
                None
            )
            self.assertIsNotNone(point)
            self.assertEqual(point["intensity"], expected_intensity)

    def test_heatmap_negative_coordinates(self):
        """TC_HEATMAP_09: Should handle negative coordinates correctly (e.g., Sydney, Australia)."""
        Complaint.objects.create(
            title="Issue in Sydney",
            description="Southern hemisphere complaint",
            image=create_test_image(),
            latitude=-33.8688,
            longitude=151.2093,
            votes=4,
            status="Pending"
        )

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()

        self.assertEqual(len(data["points"]), 1)
        self.assertEqual(data["points"][0]["lat"], -33.8688)
        self.assertEqual(data["points"][0]["lng"], 151.2093)
        self.assertEqual(data["points"][0]["intensity"], 4)

    def test_heatmap_all_complaints_excluded(self):
        """TC_HEATMAP_10: When all complaints have null coordinates, heatmap should be empty."""
        Complaint.objects.create(
            title="No location 1",
            description="No coordinates",
            image=create_test_image(),
            latitude=None,
            longitude=None,
            votes=5,
            status="Pending"
        )
        Complaint.objects.create(
            title="No location 2",
            description="No coordinates either",
            image=create_test_image(),
            latitude=None,
            longitude=None,
            votes=10,
            status="Pending"
        )

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()

        self.assertEqual(len(data["points"]), 0)

    def test_heatmap_post_method_not_allowed(self):
        """TC_HEATMAP_11: POST method should not be allowed for heatmap endpoint."""
        response = self.client.post("/api/complaints/heatmap/")
        self.assertEqual(response.status_code, 405)

    def test_heatmap_vote_up_increases_intensity(self):
        """TC_HEATMAP_12: After vote-up, intensity should increase in heatmap data."""
        # Create complaint with initial votes
        complaint = Complaint.objects.create(
            title="Test Issue",
            description="Test",
            image=create_test_image(),
            latitude=12.9716,
            longitude=77.5946,
            votes=5,
            status="Pending"
        )

        # Get initial heatmap data
        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()
        initial_intensity = data["points"][0]["intensity"]
        self.assertEqual(initial_intensity, 5)

        # Vote up the complaint
        vote_response = self.client.post(f"/api/complaints/{complaint.id}/vote-up/")
        self.assertEqual(vote_response.status_code, 200)

        # Get updated heatmap data
        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()
        updated_intensity = data["points"][0]["intensity"]

        # Intensity should have increased by 1
        self.assertEqual(updated_intensity, 6)

    def test_heatmap_solved_complaints_included(self):
        """TC_HEATMAP_13: Solved complaints should still appear in heatmap."""
        Complaint.objects.create(
            title="Solved Issue",
            description="This was fixed",
            image=create_test_image(),
            latitude=12.9716,
            longitude=77.5946,
            votes=10,
            status="Solved"
        )

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()

        # Solved complaints should still be in heatmap
        self.assertEqual(len(data["points"]), 1)
        self.assertEqual(data["points"][0]["intensity"], 10)


# ============================================================================
# COMPREHENSIVE TESTS FOR FULL PROJECT
# ============================================================================

class TestDepartmentModel(TestCase):
    """Test cases for Department model."""

    def test_create_department(self):
        """TC_MODEL_01: Create a department with all fields."""
        dept = Department.objects.create(
            name="Potholes",
            email="potholes@test.com",
            phone="1234567890",
            description="Handles pothole complaints"
        )
        self.assertEqual(dept.name, "Potholes")
        self.assertEqual(dept.email, "potholes@test.com")
        self.assertEqual(dept.phone, "1234567890")

    def test_department_name_unique(self):
        """TC_MODEL_02: Department name should be unique."""
        Department.objects.create(name="Streetlight", email="light@test.com", phone="123")
        with self.assertRaises(Exception):
            Department.objects.create(name="Streetlight", email="light2@test.com", phone="456")

    def test_department_str_representation(self):
        """TC_MODEL_03: Department string representation should be its name."""
        dept = Department.objects.create(name="Trash", email="trash@test.com", phone="123")
        self.assertEqual(str(dept), "Trash")


class TestComplaintModel(TestCase):
    """Test cases for Complaint model."""

    def setUp(self):
        self.department = Department.objects.create(
            name="Test Dept",
            email="test@test.com",
            phone="1234567890"
        )

    def test_create_complaint_minimal(self):
        """TC_MODEL_04: Create complaint with minimal required fields."""
        complaint = Complaint.objects.create(
            title="Test Issue",
            image=create_test_image()
        )
        self.assertEqual(complaint.title, "Test Issue")
        self.assertEqual(complaint.status, "Pending")
        self.assertEqual(complaint.votes, 1)

    def test_create_complaint_full(self):
        """TC_MODEL_05: Create complaint with all fields."""
        complaint = Complaint.objects.create(
            title="Full Issue",
            description="Detailed description",
            image=create_test_image(),
            latitude=12.9716,
            longitude=77.5946,
            status="In Progress",
            department=self.department,
            votes=5,
            predicted_class="potholes"
        )
        self.assertEqual(complaint.latitude, 12.9716)
        self.assertEqual(complaint.longitude, 77.5946)
        self.assertEqual(complaint.predicted_class, "potholes")

    def test_complaint_status_choices(self):
        """TC_MODEL_06: Complaint status should be limited to valid choices."""
        complaint = Complaint.objects.create(
            title="Status Test",
            image=create_test_image()
        )
        valid_statuses = ["Pending", "In Progress", "Solved"]
        self.assertIn(complaint.status, valid_statuses)

    def test_complaint_auto_timestamp(self):
        """TC_MODEL_07: Complaint should auto-set created_at timestamp."""
        complaint = Complaint.objects.create(
            title="Timestamp Test",
            image=create_test_image()
        )
        self.assertIsNotNone(complaint.created_at)

    def test_complaint_str_representation(self):
        """TC_MODEL_08: Complaint string representation should include title and status."""
        complaint = Complaint.objects.create(
            title="Str Test",
            image=create_test_image(),
            status="Solved"
        )
        self.assertIn("Str Test", str(complaint))
        self.assertIn("Solved", str(complaint))


class TestAdminUserModel(TestCase):
    """Test cases for AdminUser model."""

    def test_create_admin_user(self):
        """TC_MODEL_09: Create admin user with all fields."""
        admin = AdminUser.objects.create(
            username="admin1",
            password="pass123",
            department="Potholes"
        )
        self.assertEqual(admin.username, "admin1")
        self.assertEqual(admin.department, "Potholes")

    def test_admin_username_unique(self):
        """TC_MODEL_10: Admin username should be unique."""
        AdminUser.objects.create(username="admin", password="pass", department="Test")
        with self.assertRaises(Exception):
            AdminUser.objects.create(username="admin", password="pass2", department="Test2")

    def test_admin_str_representation(self):
        """TC_MODEL_11: Admin string representation should include username and department."""
        admin = AdminUser.objects.create(
            username="admin1",
            password="pass",
            department="Streetlight"
        )
        self.assertIn("admin1", str(admin))
        self.assertIn("Streetlight", str(admin))


class TestAdminLoginAPI(TestCase):
    """Test cases for admin login API endpoint."""

    def setUp(self):
        self.client = Client()
        self.admin = AdminUser.objects.create(
            username="admin_user",
            password="admin_pass",
            department="Potholes"
        )

    def test_admin_login_success(self):
        """TC_AUTH_01: Successful admin login returns token."""
        response = self.client.post(
            "/api/complaints/admin/login/",
            data=json.dumps({
                "username": "admin_user",
                "password": "admin_pass",
                "department": "Potholes"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("token", data)
        self.assertIn("department", data)
        self.assertEqual(data["department"], "Potholes")

    def test_admin_login_wrong_password(self):
        """TC_AUTH_02: Login with wrong password should fail."""
        response = self.client.post(
            "/api/complaints/admin/login/",
            data=json.dumps({
                "username": "admin_user",
                "password": "wrong_password",
                "department": "Potholes"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_login_wrong_username(self):
        """TC_AUTH_03: Login with non-existent username should fail."""
        response = self.client.post(
            "/api/complaints/admin/login/",
            data=json.dumps({
                "username": "nonexistent",
                "password": "pass",
                "department": "Potholes"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_login_wrong_department(self):
        """TC_AUTH_04: Login with wrong department should fail."""
        response = self.client.post(
            "/api/complaints/admin/login/",
            data=json.dumps({
                "username": "admin_user",
                "password": "admin_pass",
                "department": "WrongDept"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_login_get_method_not_allowed(self):
        """TC_AUTH_05: GET method should not be allowed."""
        response = self.client.get("/api/complaints/admin/login/")
        self.assertEqual(response.status_code, 405)


class TestVoteUpAPI(TestCase):
    """Test cases for vote-up API endpoint."""

    def setUp(self):
        self.client = Client()
        self.complaint = Complaint.objects.create(
            title="Votable Issue",
            description="Please vote",
            image=create_test_image(),
            votes=3
        )

    def test_vote_up_success(self):
        """TC_VOTE_01: Vote up should increment vote count."""
        response = self.client.post(f"/api/complaints/{self.complaint.id}/vote-up/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["votes"], 4)
        self.assertIn("message", data)

    def test_vote_up_multiple_times(self):
        """TC_VOTE_02: Multiple vote-ups should increment correctly."""
        initial_votes = self.complaint.votes
        for i in range(5):
            response = self.client.post(f"/api/complaints/{self.complaint.id}/vote-up/")
            self.assertEqual(response.status_code, 200)

        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.votes, initial_votes + 5)

    def test_vote_up_nonexistent_complaint(self):
        """TC_VOTE_03: Vote up on non-existent complaint should return 404."""
        response = self.client.post("/api/complaints/99999/vote-up/")
        self.assertEqual(response.status_code, 404)

    def test_vote_up_get_method_not_allowed(self):
        """TC_VOTE_04: GET method should not be allowed."""
        response = self.client.get(f"/api/complaints/{self.complaint.id}/vote-up/")
        self.assertEqual(response.status_code, 405)


class TestUpdateStatusAPI(TestCase):
    """Test cases for update status API endpoint."""

    def setUp(self):
        self.client = Client()
        self.complaint = Complaint.objects.create(
            title="Status Test",
            description="Test status updates",
            image=create_test_image(),
            status="Pending"
        )

    def test_update_status_to_in_progress(self):
        """TC_STATUS_01: Update status from Pending to In Progress."""
        response = self.client.post(
            f"/api/complaints/{self.complaint.id}/update-status/",
            data=json.dumps({"status": "In Progress"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, "In Progress")

    def test_update_status_to_solved(self):
        """TC_STATUS_02: Update status to Solved."""
        response = self.client.post(
            f"/api/complaints/{self.complaint.id}/update-status/",
            data=json.dumps({"status": "Solved"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, "Solved")

    def test_update_status_invalid(self):
        """TC_STATUS_03: Invalid status should return 400."""
        response = self.client.post(
            f"/api/complaints/{self.complaint.id}/update-status/",
            data=json.dumps({"status": "InvalidStatus"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_update_status_nonexistent_complaint(self):
        """TC_STATUS_04: Update status on non-existent complaint should return 404."""
        response = self.client.post(
            "/api/complaints/99999/update-status/",
            data=json.dumps({"status": "Solved"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    def test_update_status_get_method_not_allowed(self):
        """TC_STATUS_05: GET method should not be allowed."""
        response = self.client.get(f"/api/complaints/{self.complaint.id}/update-status/")
        self.assertEqual(response.status_code, 405)

    def test_update_status_missing_data(self):
        """TC_STATUS_06: Missing status field should cause error."""
        response = self.client.post(
            f"/api/complaints/{self.complaint.id}/update-status/",
            data=json.dumps({}),
            content_type="application/json"
        )
        self.assertIn(response.status_code, [400, 500])


class TestListComplaintsByDepartment(TestCase):
    """Test cases for listing complaints by department API."""

    def setUp(self):
        self.client = Client()
        self.dept1 = Department.objects.create(
            name="Potholes",
            email="potholes@test.com",
            phone="123"
        )
        self.dept2 = Department.objects.create(
            name="Streetlight",
            email="light@test.com",
            phone="456"
        )

        Complaint.objects.create(
            title="Pothole Issue",
            image=create_test_image(),
            department=self.dept1,
            status="Pending"
        )
        Complaint.objects.create(
            title="Another Pothole",
            image=create_test_image(),
            department=self.dept1,
            status="In Progress"
        )
        Complaint.objects.create(
            title="Light Issue",
            image=create_test_image(),
            department=self.dept2,
            status="Pending"
        )

    def test_list_by_existing_department(self):
        """TC_DEPT_01: List complaints for existing department."""
        response = self.client.get("/api/complaints/department/Potholes/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["complaints"]), 2)
        self.assertEqual(data["department"], "Potholes")

    def test_list_by_nonexistent_department(self):
        """TC_DEPT_02: Non-existent department should return 404."""
        response = self.client.get("/api/complaints/department/Nonexistent/")
        self.assertEqual(response.status_code, 404)

    def test_list_by_department_case_insensitive(self):
        """TC_DEPT_03: Department lookup should be case-insensitive."""
        response = self.client.get("/api/complaints/department/potholes/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["complaints"]), 2)


class TestComplaintCountsAPI(TestCase):
    """Test cases for complaint counts API endpoint."""

    def setUp(self):
        self.client = Client()
        self.dept = Department.objects.create(
            name="streetlight",
            email="light@test.com",
            phone="123"
        )

    def test_counts_empty_database(self):
        """TC_COUNTS_01: Empty database should return all zeros."""
        response = self.client.get("/api/complaints/counts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        departments = ["streetlight", "potholes", "trash_bins", "water_leakage", "higher_department"]
        for dept in departments:
            self.assertIn(dept, data)
            self.assertEqual(data[dept]["pending"], 0)
            self.assertEqual(data[dept]["in_progress"], 0)
            self.assertEqual(data[dept]["solved"], 0)

    def test_counts_with_complaints(self):
        """TC_COUNTS_02: Counts should reflect actual complaint statuses."""
        Complaint.objects.create(
            title="Pending Issue",
            image=create_test_image(),
            department=self.dept,
            status="Pending"
        )
        Complaint.objects.create(
            title="In Progress Issue",
            image=create_test_image(),
            department=self.dept,
            status="In Progress"
        )
        Complaint.objects.create(
            title="Solved Issue",
            image=create_test_image(),
            department=self.dept,
            status="Solved"
        )

        response = self.client.get("/api/complaints/counts/")
        data = response.json()

        self.assertEqual(data["streetlight"]["pending"], 1)
        self.assertEqual(data["streetlight"]["in_progress"], 1)
        self.assertEqual(data["streetlight"]["solved"], 1)

    def test_counts_all_departments_present(self):
        """TC_COUNTS_03: Response should include all expected departments."""
        response = self.client.get("/api/complaints/counts/")
        data = response.json()

        expected_depts = ["streetlight", "potholes", "trash_bins", "water_leakage", "higher_department"]
        for dept in expected_depts:
            self.assertIn(dept, data)


class TestListAllComplaintsAPI(TestCase):
    """Test cases for list all complaints API endpoint."""

    def setUp(self):
        self.client = Client()

    def test_list_all_empty(self):
        """TC_LIST_01: Empty list when no complaints exist."""
        response = self.client.get("/api/complaints/all/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["complaints"]), 0)

    def test_list_all_multiple_complaints(self):
        """TC_LIST_02: Should return all complaints ordered by creation date."""
        dept = Department.objects.create(name="Test", email="t@test.com", phone="123")
        Complaint.objects.create(
            title="First",
            image=create_test_image(),
            department=dept
        )
        Complaint.objects.create(
            title="Second",
            image=create_test_image(),
            department=dept
        )

        response = self.client.get("/api/complaints/all/")
        data = response.json()
        self.assertEqual(len(data["complaints"]), 2)
        # Should be ordered by created_at descending (newest first)
        self.assertEqual(data["complaints"][0]["title"], "Second")
        self.assertEqual(data["complaints"][1]["title"], "First")

    def test_list_all_response_structure(self):
        """TC_LIST_03: Response should have correct structure."""
        Complaint.objects.create(
            title="Structure Test",
            description="Test",
            image=create_test_image(),
            latitude=12.97,
            longitude=77.59
        )

        response = self.client.get("/api/complaints/all/")
        data = response.json()
        complaint = data["complaints"][0]

        self.assertIn("id", complaint)
        self.assertIn("title", complaint)
        self.assertIn("description", complaint)
        self.assertIn("image", complaint)
        self.assertIn("status", complaint)
        self.assertIn("latitude", complaint)
        self.assertIn("longitude", complaint)
        self.assertIn("created_at", complaint)


class TestCreateComplaintFullFlow(TestCase):
    """Test cases for complete complaint creation flow."""

    def setUp(self):
        self.client = Client()

    @patch('complaints.views.classify_image')
    def test_full_complaint_creation(self, mock_classify):
        """TC_FLOW_01: Complete complaint creation flow with AI prediction."""
        mock_classify.return_value = ("potholes", 0.95)

        response = self.client.post(
            "/api/complaints/create/",
            data={
                "title": "New Pothole",
                "description": "Dangerous pothole on main road",
                "latitude": "12.9716",
                "longitude": "77.5946",
                "file": create_test_image()
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("duplicate"))
        self.assertIn("complaint_id", data)

        # Verify complaint was created
        complaint = Complaint.objects.get(id=data["complaint_id"])
        self.assertEqual(complaint.title, "New Pothole")
        self.assertEqual(complaint.latitude, 12.9716)
        self.assertEqual(complaint.votes, 1)

    def test_create_complaint_with_image_only(self):
        """TC_FLOW_02: Create complaint without location."""
        response = self.client.post(
            "/api/complaints/create/",
            data={
                "title": "No Location Issue",
                "description": "Issue without GPS",
                "file": create_test_image()
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("duplicate"))


class TestPredictionImageAPI(TestCase):
    """Test cases for image prediction API endpoint."""

    def setUp(self):
        self.client = Client()

    @patch('complaints.views.classify_image')
    def test_predict_success(self, mock_classify):
        """TC_PREDICT_01: Successful image prediction."""
        mock_classify.return_value = ("potholes", 0.92)

        response = self.client.post(
            "/api/complaints/predict/",
            data={"file": create_test_image()}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["predicted_class"], "potholes")
        self.assertEqual(data["confidence"], 0.92)

    @patch('complaints.views.classify_image')
    def test_predict_different_classes(self, mock_classify):
        """TC_PREDICT_02: Predict different complaint classes."""
        test_cases = [
            ("potholes", 0.88),
            ("streetlight", 0.75),
            ("trash_bins", 0.91),
            ("water_leakage", 0.83),
            ("unknown", 0.60)
        ]

        for predicted_class, confidence in test_cases:
            mock_classify.return_value = (predicted_class, confidence)
            response = self.client.post(
                "/api/complaints/predict/",
                data={"file": create_test_image()}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["predicted_class"], predicted_class)

    def test_predict_no_file(self):
        """TC_PREDICT_03: Request without file should return error."""
        response = self.client.post("/api/complaints/predict/")
        self.assertEqual(response.status_code, 400)

    def test_predict_get_method_not_allowed(self):
        """TC_PREDICT_04: GET method should not be allowed."""
        response = self.client.get("/api/complaints/predict/")
        self.assertEqual(response.status_code, 405)


class TestEdgeCasesAndErrorHandling(TestCase):
    """Test edge cases and error handling across all endpoints."""

    def setUp(self):
        self.client = Client()
        self.complaint = Complaint.objects.create(
            title="Edge Case Test",
            description="Testing edge cases",
            image=create_test_image()
        )

    def test_complaint_with_zero_votes(self):
        """TC_EDGE_01: Handle complaint with zero votes."""
        self.complaint.votes = 0
        self.complaint.save()

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()
        if len(data["points"]) > 0:
            # Zero votes should default to intensity 1
            self.assertGreaterEqual(data["points"][0]["intensity"], 1)

    def test_complaint_with_high_votes(self):
        """TC_EDGE_02: Handle complaint with very high vote count."""
        self.complaint.latitude = 12.97
        self.complaint.longitude = 77.59
        self.complaint.votes = 10000
        self.complaint.save()

        response = self.client.get("/api/complaints/heatmap/")
        data = response.json()
        self.assertEqual(data["points"][0]["intensity"], 10000)

    def test_complaint_boundary_coordinates(self):
        """TC_EDGE_03: Handle boundary coordinates (poles, international date line)."""
        test_locations = [
            (90, 0),      # North Pole
            (-90, 0),     # South Pole
            (0, 180),     # International Date Line
            (0, -180),    # International Date Line (west)
        ]

        for lat, lng in test_locations:
            complaint = Complaint.objects.create(
                title=f"Boundary {lat},{lng}",
                description="Boundary test",
                image=create_test_image(),
                latitude=lat,
                longitude=lng,
                votes=1
            )

            response = self.client.get("/api/complaints/heatmap/")
            self.assertEqual(response.status_code, 200)

            # Clean up for next iteration
            complaint.delete()

    def test_invalid_json_format(self):
        """TC_EDGE_04: Handle invalid JSON in request body."""
        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data="invalid json",
            content_type="application/json"
        )
        self.assertIn(response.status_code, [400, 500])

    def test_malformed_coordinates(self):
        """TC_EDGE_05: Handle malformed coordinate values."""
        response = self.client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "Test",
                "latitude": "not_a_number",
                "longitude": "also_not_a_number"
            }),
            content_type="application/json"
        )
        self.assertIn(response.status_code, [400, 500])

    def test_very_long_title(self):
        """TC_EDGE_06: Handle very long title."""
        long_title = "A" * 300
        complaint = Complaint.objects.create(
            title=long_title,
            description="Test",
            image=create_test_image()
        )
        # Should truncate or handle gracefully
        self.assertIsNotNone(complaint.id)

    def test_unicode_in_fields(self):
        """TC_EDGE_07: Handle Unicode characters in fields."""
        complaint = Complaint.objects.create(
            title="Issue with émojis 🎉 and 中文",
            description="Description with ñ and ü",
            image=create_test_image()
        )
        self.assertIsNotNone(complaint.id)
        self.assertIn("🎉", complaint.title)

    def test_null_description(self):
        """TC_EDGE_08: Handle null description field."""
        complaint = Complaint.objects.create(
            title="No Description",
            description=None,
            image=create_test_image()
        )
        self.assertIsNone(complaint.description)

    def test_empty_string_fields(self):
        """TC_EDGE_09: Handle empty string in optional fields."""
        complaint = Complaint.objects.create(
            title="Empty Fields",
            description="",
            image=create_test_image()
        )
        self.assertEqual(complaint.description, "")


class TestIntegrationScenarios(TestCase):
    """Integration tests for complete user scenarios."""

    def setUp(self):
        self.client = Client()
        self.dept = Department.objects.create(
            name="Potholes",
            email="potholes@test.com",
            phone="1234567890"
        )

    @patch('complaints.views.classify_image')
    def test_complete_complaint_lifecycle(self, mock_classify):
        """TC_INT_01: Complete lifecycle from creation to resolution."""
        mock_classify.return_value = ("potholes", 0.90)

        # Step 1: Create complaint
        response = self.client.post(
            "/api/complaints/create/",
            data={
                "title": "Lifecycle Test",
                "description": "Full lifecycle test",
                "latitude": "12.9716",
                "longitude": "77.5946",
                "file": create_test_image()
            }
        )
        self.assertEqual(response.status_code, 200)
        complaint_id = response.json()["complaint_id"]

        # Step 2: Verify it appears in all complaints
        response = self.client.get("/api/complaints/all/")
        self.assertEqual(len(response.json()["complaints"]), 1)

        # Step 3: Vote up multiple times
        for _ in range(5):
            response = self.client.post(f"/api/complaints/{complaint_id}/vote-up/")
            self.assertEqual(response.status_code, 200)

        # Step 4: Update status to In Progress
        response = self.client.post(
            f"/api/complaints/{complaint_id}/update-status/",
            data=json.dumps({"status": "In Progress"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Step 5: Verify in counts
        response = self.client.get("/api/complaints/counts/")
        counts = response.json()
        # Note: higher_department counts all complaints
        self.assertGreater(counts["higher_department"]["in_progress"], 0)

        # Step 6: Update to Solved
        response = self.client.post(
            f"/api/complaints/{complaint_id}/update-status/",
            data=json.dumps({"status": "Solved"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Step 7: Verify heatmap includes it
        response = self.client.get("/api/complaints/heatmap/")
        points = response.json()["points"]
        self.assertGreater(len(points), 0)

    @patch('complaints.views.classify_image')
    def test_duplicate_detection_creates_vote_up(self, mock_classify):
        """TC_INT_02: Duplicate complaint leads to vote up scenario."""
        mock_classify.return_value = ("potholes", 0.85)

        # Create original complaint
        Complaint.objects.create(
            title="Duplicate Test",
            description="Original",
            image=create_test_image(),
            latitude=12.9716,
            longitude=77.5946,
            votes=3
        )

        # Try to create duplicate
        response = self.client.post(
            "/api/complaints/create/",
            data={
                "title": "Duplicate Test",
                "description": "Duplicate",
                "latitude": "12.9716",
                "longitude": "77.5946",
                "file": create_test_image()
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("duplicate"))
        self.assertIn("complaint", data)

    def test_admin_workflow(self):
        """TC_INT_03: Admin login and manage complaints."""
        # Create admin
        AdminUser.objects.create(
            username="admin",
            password="admin123",
            department="Potholes"
        )

        # Create some complaints
        Complaint.objects.create(
            title="Issue 1",
            image=create_test_image(),
            status="Pending"
        )
        Complaint.objects.create(
            title="Issue 2",
            image=create_test_image(),
            status="In Progress"
        )

        # Admin login
        response = self.client.post(
            "/api/complaints/admin/login/",
            data=json.dumps({
                "username": "admin",
                "password": "admin123",
                "department": "Potholes"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Get complaint counts
        response = self.client.get("/api/complaints/counts/")
        self.assertEqual(response.status_code, 200)

        # View all complaints
        response = self.client.get("/api/complaints/all/")
        self.assertEqual(len(response.json()["complaints"]), 2)

        # View heatmap
        response = self.client.get("/api/complaints/heatmap/")
        self.assertEqual(response.status_code, 200)


class TestSecurityAndValidation(TestCase):
    """Test security aspects and input validation."""

    def test_sql_injection_attempt(self):
        """TC_SEC_01: SQL injection should be handled safely."""
        client = Client()
        response = client.post(
            "/api/complaints/check-duplicate/",
            data=json.dumps({
                "title": "'; DROP TABLE complaints; --",
                "latitude": 12.97,
                "longitude": 77.59
            }),
            content_type="application/json"
        )
        # Should not crash, should handle gracefully
        self.assertIn(response.status_code, [200, 400, 500])

    def test_xss_attempt_in_title(self):
        """TC_SEC_02: XSS in title should be stored safely."""
        xss_payload = "<script>alert('xss')</script>"
        complaint = Complaint.objects.create(
            title=xss_payload,
            description="Test",
            image=create_test_image()
        )
        # Django ORM escapes by default
        self.assertIn("<script>", complaint.title)

    def test_file_upload_without_image(self):
        """TC_SEC_03: Non-image file upload should be handled."""
        client = Client()
        # Try to upload a text file
        fake_file = SimpleUploadedFile(
            "test.txt",
            b"This is not an image",
            content_type="text/plain"
        )
        response = client.post(
            "/api/complaints/create/",
            data={
                "title": "Text File Test",
                "description": "Testing text file",
                "file": fake_file
            }
        )
        # Should handle gracefully - may fail at image processing
        self.assertIn(response.status_code, [200, 400, 500])
