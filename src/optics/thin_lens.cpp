// SPDX-License-Identifier: GPL-3.0-or-later
#include "optics/thin_lens.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace tilt_shift {
namespace {
constexpr double pi = 3.141592653589793238462643383279502884;
constexpr double geometry_epsilon = 64.0 * std::numeric_limits<double>::epsilon();

void require(bool condition, const char *message)
{
  if (!condition) {
    throw std::invalid_argument(message);
  }
}
bool finite(Vec3 a)
{
  return std::isfinite(a.x) && std::isfinite(a.y) && std::isfinite(a.z);
}
void interval(double x, double lo, double hi, const char *message)
{
  require(std::isfinite(x) && x >= lo && x <= hi, message);
}
Vec3 rotate(Vec3 v, double tilt, double swing, double axis)
{
  const double ct = std::cos(tilt), st = std::sin(tilt);
  const double cs = std::cos(swing), ss = std::sin(swing);
  const double ca = std::cos(axis), sa = std::sin(axis);
  const Vec3 rx{v.x, ct * v.y - st * v.z, st * v.y + ct * v.z};
  const Vec3 ry{cs * rx.x + ss * rx.z, rx.y, -ss * rx.x + cs * rx.z};
  return {ca * ry.x - sa * ry.y, sa * ry.x + ca * ry.y, ry.z};
}
} // namespace

Vec3 operator+(Vec3 a, Vec3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
Vec3 operator-(Vec3 a, Vec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
Vec3 operator*(Vec3 a, double s) { return {a.x * s, a.y * s, a.z * s}; }
Vec3 operator/(Vec3 a, double s) { return {a.x / s, a.y / s, a.z / s}; }
double dot(Vec3 a, Vec3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
Vec3 cross(Vec3 a, Vec3 b)
{
  return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z,
          a.x * b.y - a.y * b.x};
}
double length(Vec3 a) { return std::hypot(a.x, a.y, a.z); }
Vec3 normalized(Vec3 a)
{
  const double size = length(a);
  require(finite(a) && std::isfinite(size) && size > 0.0,
          "Cannot normalize a zero or nonfinite vector");
  return a / size;
}

ThinLens::ThinLens(Parameters p) : parameters_(p)
{
  require(std::isfinite(p.focal_length) && p.focal_length > 0.0,
          "Focal length must be positive and finite");
  require(p.focus_distance > 0.0 && !std::isnan(p.focus_distance),
          "Focus distance must be positive (positive infinity is allowed)");
  require(std::isfinite(p.sensor_width) && p.sensor_width > 0.0 &&
              std::isfinite(p.sensor_height) && p.sensor_height > 0.0,
          "Sensor dimensions must be positive and finite");
  require(std::isfinite(p.shift_x) && std::isfinite(p.shift_y),
          "Sensor shift must be finite");
  require(std::isfinite(p.tilt) && std::isfinite(p.swing) &&
              std::isfinite(p.axis_rotation), "Rotations must be finite");
  require(std::isfinite(p.aperture_radius) && p.aperture_radius >= 0.0,
          "Aperture radius must be nonnegative and finite");
  require(p.image_circle_radius >= 0.0 && !std::isnan(p.image_circle_radius),
          "Coverage radius must be nonnegative (positive infinity disables clipping)");
  aperture_x_ = rotate({1, 0, 0}, p.tilt, p.swing, p.axis_rotation);
  aperture_y_ = rotate({0, 1, 0}, p.tilt, p.swing, p.axis_rotation);
  normal_ = rotate({0, 0, 1}, p.tilt, p.swing, p.axis_rotation);
  require(normal_.z > geometry_epsilon, "Lens must face the scene, away from grazing");
  const double denominator = normal_.z - p.focal_length / p.focus_distance;
  require(std::isfinite(denominator) && denominator > geometry_epsilon,
          "Requested focus requires a nonpositive or singular sensor distance");
  sensor_distance_ = p.focal_length / denominator;
  require(std::isfinite(sensor_distance_), "Sensor distance overflow");

  // Reject a sensor crossing or grazing the lens plane, including its corners.
  const double corner_max = normal_.x * p.shift_x + normal_.y * p.shift_y +
      std::abs(normal_.x) * p.sensor_width * 0.5 +
      std::abs(normal_.y) * p.sensor_height * 0.5 - normal_.z * sensor_distance_;
  const double scale = std::max({p.focal_length, sensor_distance_, p.sensor_width,
      p.sensor_height, std::abs(p.shift_x), std::abs(p.shift_y), p.aperture_radius});
  require(std::isfinite(corner_max) && corner_max < -geometry_epsilon * scale,
          "Sensor rectangle crosses or grazes the lens plane");
  const double aperture_z_extent = p.aperture_radius *
      std::hypot(aperture_x_.z, aperture_y_.z);
  require(std::isfinite(aperture_z_extent) &&
              sensor_distance_ - aperture_z_extent > geometry_epsilon * scale,
          "Aperture crosses or grazes the sensor plane");
}

Plane ThinLens::focus_plane() const
{
  return {normal_ - Vec3{0, 0, parameters_.focal_length / sensor_distance_},
          parameters_.focal_length};
}

Vec3 ThinLens::sensor_point(double x, double y) const
{
  interval(x, -1, 1, "Sensor X must be in [-1,1]");
  interval(y, -1, 1, "Sensor Y must be in [-1,1]");
  return {parameters_.shift_x + x * parameters_.sensor_width * 0.5,
          parameters_.shift_y + y * parameters_.sensor_height * 0.5,
          -sensor_distance_};
}

Conjugate ThinLens::conjugate(double x, double y) const
{
  const Vec3 p = sensor_point(x, y);
  return {p, 1.0 + dot(normal_, p) / parameters_.focal_length};
}

bool ThinLens::covered_point(Vec3 p) const
{
  if (std::isinf(parameters_.image_circle_radius)) {
    return true;
  }
  // Chief ray intersection with the rear focal plane, measured from -f*n.
  const Vec3 rear = p * (-parameters_.focal_length / dot(normal_, p));
  return length(rear + normal_ * parameters_.focal_length) <=
         parameters_.image_circle_radius;
}

bool ThinLens::covered(double x, double y) const
{
  return covered_point(sensor_point(x, y));
}

Ray ThinLens::ray_from_aperture(Vec3 p, Vec3 a) const
{
  const double h = 1.0 + dot(normal_, p) / parameters_.focal_length;
  // Homogeneous expression avoids division by h at infinity. n.d = -n.p > 0.
  return {a, normalized(a * h - p), covered_point(p) ? 1.0 : 0.0};
}

Ray ThinLens::ray_at(double x, double y, double disk_x, double disk_y) const
{
  require(std::isfinite(disk_x) && std::isfinite(disk_y) &&
              std::hypot(disk_x, disk_y) <= 1.0,
          "Aperture coordinates must lie in the unit disk");
  const Vec3 a = (aperture_x_ * disk_x + aperture_y_ * disk_y) *
                 parameters_.aperture_radius;
  return ray_from_aperture(sensor_point(x, y), a);
}

Ray ThinLens::sample_ray(double x, double y, double u, double v) const
{
  interval(u, 0, 1, "Aperture U must be in [0,1]");
  interval(v, 0, 1, "Aperture V must be in [0,1]");
  const double r = parameters_.aperture_radius * std::sqrt(u);
  const double phi = 2.0 * pi * v;
  return ray_from_aperture(sensor_point(x, y),
      aperture_x_ * (r * std::cos(phi)) + aperture_y_ * (r * std::sin(phi)));
}
} // namespace tilt_shift
