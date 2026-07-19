import { LegacyStudio } from "@/components/legacy-studio";
import { ServiceWorkerRegister } from "@/components/service-worker-register";

export default function Page() {
  return <><LegacyStudio /><ServiceWorkerRegister /></>;
}
