/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  experimental: {
    // 👇 Add your EC2 IP here or '*' if testing
    allowedDevOrigins: ["http://51.20.18.59:8080"],
  },
}

export default nextConfig
