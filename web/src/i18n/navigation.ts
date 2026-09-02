import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

// Use these instead of next/link and next/navigation throughout the app —
// they keep the /en or /fil prefix on every navigation automatically.
export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
