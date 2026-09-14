"use client";

import { useParams } from "next/navigation";
import JobDetailPage from "../../jobs/[id]/page";

/** Re-use job detail UI under the tech mobile route. */
export default function TechJobPage() {
  useParams();
  return <JobDetailPage />;
}
