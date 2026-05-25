import unittest

import numpy as np

from spectrometer_core import ExtractionSettings, spectrum_from_frame, update_settings


class SpectrumExtractionTests(unittest.TestCase):
    def test_extracts_horizontal_gradient(self):
        width = 16
        frame = np.zeros((8, width, 3), dtype=np.uint8)
        gradient = np.arange(width, dtype=np.uint8)
        frame[:, :, 0] = gradient
        frame[:, :, 1] = gradient
        frame[:, :, 2] = gradient

        settings = ExtractionSettings(frame_width=width, frame_height=8, output_width=width, row_center_y=4, half_height=0)
        spectrum = spectrum_from_frame(frame, settings)

        np.testing.assert_array_equal(spectrum, gradient)

    def test_averages_band_height(self):
        frame = np.zeros((5, 6, 3), dtype=np.uint8)
        for row in range(5):
            frame[row, :, :] = row * 10

        settings = ExtractionSettings(frame_width=6, frame_height=5, output_width=6, row_center_y=2, half_height=1)
        spectrum = spectrum_from_frame(frame, settings)

        np.testing.assert_array_equal(spectrum, np.full(6, 20, dtype=np.uint8))

    def test_rotated_row_tracks_vertical_change(self):
        frame = np.zeros((40, 40, 3), dtype=np.uint8)
        for row in range(40):
            frame[row, :, :] = row

        settings = ExtractionSettings(frame_width=40, frame_height=40, output_width=40, row_center_y=20, half_height=0, angle_degrees=20)
        spectrum = spectrum_from_frame(frame, settings)

        self.assertLess(int(spectrum[0]), int(spectrum[-1]))
        self.assertAlmostEqual(int(spectrum[20]), 20, delta=2)

    def test_reverse_x_is_explicit(self):
        width = 8
        frame = np.zeros((4, width, 3), dtype=np.uint8)
        gradient = np.arange(width, dtype=np.uint8)
        frame[:, :, :] = gradient[None, :, None]

        settings = ExtractionSettings(frame_width=width, frame_height=4, output_width=width, row_center_y=1, half_height=0, reverse_x=True)
        spectrum = spectrum_from_frame(frame, settings)

        np.testing.assert_array_equal(spectrum, gradient[::-1])

    def test_settings_are_clamped(self):
        settings = update_settings(
            ExtractionSettings(frame_width=10, frame_height=10),
            {
                "row_center_y": 99,
                "half_height": -4,
                "angle_degrees": 90,
                "gain": 100,
            },
        )

        self.assertEqual(settings.row_center_y, 9)
        self.assertEqual(settings.half_height, 0)
        self.assertEqual(settings.angle_degrees, 45)
        self.assertEqual(settings.gain, 32)


if __name__ == "__main__":
    unittest.main()
