import withPWA from "@ducanh2912/next-pwa";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["100.124.11.63", "chi"],
  turbopack: {
    root: __dirname,
  },
};

export default withPWA({
  dest: "public",
  cacheOnFrontEndNav: true,
  aggressiveFrontEndNavCaching: false,
  disable: process.env.NODE_ENV === "development",
  runtimeCaching: [
    {
      // NetworkFirst for API GET routes (10s timeout, then cache fallback).
      // NOTE: POST /api/chat is NOT matched — method filter is implicit via
      // GET-only cache; the SW passes POST requests through unchanged.
      urlPattern: /^\/api\/.*/i,
      handler: "NetworkFirst",
      options: {
        cacheName: "aria-api-cache",
        networkTimeoutSeconds: 10,
        expiration: { maxEntries: 50, maxAgeSeconds: 300 },
      },
    },
    {
      // StaleWhileRevalidate for Next.js static chunks.
      urlPattern: /^\/_next\/static\/.*/i,
      handler: "StaleWhileRevalidate",
      options: {
        cacheName: "aria-static-cache",
        expiration: { maxEntries: 200, maxAgeSeconds: 30 * 24 * 60 * 60 },
      },
    },
    {
      // CacheFirst for icons and public assets.
      urlPattern: /^\/icons\/.*/i,
      handler: "CacheFirst",
      options: {
        cacheName: "aria-assets-cache",
        expiration: { maxEntries: 30, maxAgeSeconds: 7 * 24 * 60 * 60 },
      },
    },
  ],
})(nextConfig);
