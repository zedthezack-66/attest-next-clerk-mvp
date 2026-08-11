import ReviewEditor from "./review-editor";
import { readStore } from "../../../../lib/store";

export default async function CandidateReview({ params }: { params: { candidateId: string } }) {
  const store = await readStore();
  const application = store.applications.find((app) => app.id === params.candidateId);
  const profile = store.profiles.find((item) => item.applicationId === params.candidateId);
  const documents = store.documents.filter((doc) => doc.applicationId === params.candidateId).map((doc) => ({
    document: doc,
    latestExtraction: store.extractions.filter((result) => result.documentId === doc.id).at(-1),
  }));
  return <ReviewEditor initial={{ application, profile, documents }} applicationId={params.candidateId} />;
}

