// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <limits>

namespace tilt_shift {

// Right-handed lens-local coordinates: +X right, +Y down, +Z toward the scene
// when viewed from behind the camera toward the scene.
// All lengths use one common unit (examples/tests use metres); angles are radians.
struct Vec3 {
  double x, y, z;
};
Vec3 operator+(Vec3 a, Vec3 b);
Vec3 operator-(Vec3 a, Vec3 b);
Vec3 operator*(Vec3 a, double s);
Vec3 operator/(Vec3 a, double s);
double dot(Vec3 a, Vec3 b);
Vec3 cross(Vec3 a, Vec3 b);
double length(Vec3 a);
Vec3 normalized(Vec3 a);

struct Parameters {
  double focal_length = 0.050;
  // Distance from lens centre along fixed camera +Z, not the rotated lens axis.
  double focus_distance = 5.0; // Positive infinity is supported.
  double sensor_width = 0.036;
  double sensor_height = 0.024;
  double shift_x = 0.0; // Physical sensor centre displacement, not Blender units.
  double shift_y = 0.0;
  double tilt = 0.0; // Rx, then Ry(swing), then Rz(axis_rotation).
  double swing = 0.0;
  double axis_rotation = 0.0;
  double aperture_radius = 0.00625; // f/4 for the default focal length.
  // Hard coverage radius at rear focal plane, not at the moving sensor plane.
  double image_circle_radius = std::numeric_limits<double>::infinity();
};

struct Plane {
  Vec3 normal; // Not normalized; dot(normal, point) == offset.
  // Zero normal with nonzero offset represents the plane at infinity.
  double offset;
};

struct Conjugate {
  // Homogeneous scene point: numerator / denominator. Zero denominator means
  // infinity; a negative denominator is a real conjugate in front of the lens.
  Vec3 numerator;
  double denominator;
};

struct Ray {
  Vec3 origin;
  Vec3 direction; // Unit scene-going direction.
  double weight; // Binary coverage only; no exposure/radiometric interpretation.
};

class ThinLens {
 public:
  // Throws std::invalid_argument on invalid or numerically singular geometry.
  explicit ThinLens(Parameters parameters);

  const Parameters &parameters() const { return parameters_; }
  double sensor_distance() const { return sensor_distance_; }
  Vec3 normal() const { return normal_; }
  Vec3 aperture_x() const { return aperture_x_; }
  Vec3 aperture_y() const { return aperture_y_; }
  Plane focus_plane() const;

  // Sensor coordinates are normalized [-1,1], with +Y physically down. Physical
  // inversion means positive sensor X sees negative scene X at zero tilt.
  Vec3 sensor_point(double sensor_x, double sensor_y) const;
  Conjugate conjugate(double sensor_x, double sensor_y) const;
  bool covered(double sensor_x, double sensor_y) const;

  // Disk coordinates are physical aperture fractions; x*x+y*y <= 1.
  Ray ray_at(double sensor_x, double sensor_y, double disk_x, double disk_y) const;
  // Uniform area sampling: both aperture variates in [0,1].
  Ray sample_ray(double sensor_x, double sensor_y, double aperture_u,
                 double aperture_v) const;

 private:
  Ray ray_from_aperture(Vec3 sensor, Vec3 aperture) const;
  bool covered_point(Vec3 sensor) const;
  Parameters parameters_;
  Vec3 normal_, aperture_x_, aperture_y_;
  double sensor_distance_;
};

} // namespace tilt_shift
