import React from "react";
import { Navigate } from "react-router-dom";

export default function RequireAuth_yyr({ children }) {
    const token = localStorage.getItem("auth_token");
    if (!token) return <Navigate to="/login" replace />;
    return children;
}
