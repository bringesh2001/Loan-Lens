import { useState } from "react";
import LandingPage from "@/components/LandingPage";
import Dashboard from "@/components/Dashboard";

const Index = () => {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  if (uploadedFile) {
    return (
      <Dashboard
        fileName={uploadedFile.name}
        onBack={() => setUploadedFile(null)}
      />
    );
  }

  return <LandingPage onFileUpload={setUploadedFile} />;
};

export default Index;
