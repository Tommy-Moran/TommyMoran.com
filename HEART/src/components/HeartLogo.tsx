import React from "react";

const HEART_GRADIENT = (
  <linearGradient id="heartGradient" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stopColor="#2a437a" />
    <stop offset="100%" stopColor="#23456a" />
  </linearGradient>
);

const TEXT_COLOR = "#fff";

const HeartLogo: React.FC<{ size?: number }> = ({ size = 160 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 160 160"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    style={{ display: "block", margin: "0 auto" }}
  >
    <defs>{HEART_GRADIENT}</defs>
    {/* Modern heart shape with gradient */}
    <path
      d="M80 140s-48-32-48-66C32 44 60 36 80 60 100 36 128 44 128 74c0 34-48 66-48 66z"
      fill="url(#heartGradient)"
      stroke="#23456a"
      strokeWidth="2"
    />
    {/* Echo arcs (right, higher, more dynamic) */}
    <path
      d="M130 70c10 8 10 22 0 30"
      stroke="#23456a"
      strokeWidth="2.5"
      strokeLinecap="round"
      fill="none"
    />
    <path
      d="M140 66c14 12 14 32 0 44"
      stroke="#23456a"
      strokeWidth="1.5"
      strokeLinecap="round"
      fill="none"
    />
    {/* Text, bold, geometric sans-serif, perfectly centered */}
    <text
      x="80"
      y="92"
      textAnchor="middle"
      fill={TEXT_COLOR}
      fontSize="36"
      fontWeight="700"
      fontFamily="'Montserrat', 'Inter', Arial, sans-serif"
      letterSpacing="4"
      style={{ userSelect: "none" }}
      dominantBaseline="middle"
    >
      HEART
    </text>
  </svg>
);

export default HeartLogo; 