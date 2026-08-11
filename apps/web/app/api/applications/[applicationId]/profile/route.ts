import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { readStore, writeStore } from "../../../../../lib/store";

export async function PATCH(request: Request, { params }: { params: { applicationId: string } }) {
  const { userId } = await auth();
  if (!userId) return new NextResponse("Unauthorized", { status: 401 });
  const body = await request.json();
  const store = await readStore();
  const index = store.profiles.findIndex((profile) => profile.applicationId === params.applicationId);
  if (index === -1) return new NextResponse("Profile not found", { status: 404 });
  store.profiles[index] = {
    ...store.profiles[index],
    bio: body.bio ?? {},
    education: body.education ?? [],
    experience: body.experience ?? [],
    skills: body.skills ?? [],
    links: body.links ?? [],
    lastEditedBy: userId,
    lastEditedAt: new Date().toISOString(),
  };
  await writeStore(store);
  return NextResponse.json(store.profiles[index]);
}
