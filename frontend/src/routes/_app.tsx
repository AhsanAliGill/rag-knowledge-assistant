import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { AppSidebar } from "@/components/AppSidebar";

export const Route = createFileRoute("/_app")({
  beforeLoad: () => {
    if (!localStorage.getItem("user")) {
      throw redirect({ to: "/login" });
    }
  },
  component: AppLayout,
});

function AppLayout() {
  return (
    <div className="min-h-screen text-[#1A1B41]">
      <AppSidebar />
      <main className="md:ml-60 p-6 md:p-8 pt-16 md:pt-8">
        <Outlet />
      </main>
    </div>
  );
}
