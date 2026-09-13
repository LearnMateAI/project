import { useState } from "react";
import { useAuth } from "../context/useAuth.js";

const SUBJECTS = [
  "Mathematics",
  "Science",
  "Technology",
  "Business",
  "Languages",
  "General",
];

function MyAccountSettings() {
  const { user } = useAuth();
  const [form, setForm] = useState({
    name: user?.name || "",
    defaultSubject: "General",
    evaluateByDefault: true,
  });
  const [saved, setSaved] = useState(false);

  function handleChange(e) {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
    setSaved(false);
  }

  function handleSave(e) {
    e.preventDefault();
    // Preferences are stored in localStorage since there is no backend endpoint for user settings.
    localStorage.setItem("learnmate_prefs", JSON.stringify({
      defaultSubject: form.defaultSubject,
      evaluateByDefault: form.evaluateByDefault,
    }));
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  return (
    <div className="animate-fade-in max-w-2xl">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Manage your profile and preferences</p>
      </div>

      <form onSubmit={handleSave}>
        {/* Profile */}
        <div className="card p-6 mb-6">
          <h2 className="text-[15px] font-semibold text-heading mb-4">Profile Information</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-[13px] font-medium text-heading mb-1.5" htmlFor="settings-name">
                Display Name
              </label>
              <input
                id="settings-name"
                name="name"
                value={form.name}
                onChange={handleChange}
                className="input"
                placeholder="Your name"
              />
            </div>
            <div>
              <label className="block text-[13px] font-medium text-heading mb-1.5" htmlFor="settings-email">
                Email Address
              </label>
              <input
                id="settings-email"
                value={user?.email || ""}
                disabled
                className="input bg-background text-muted cursor-not-allowed"
              />
              <p className="text-[11px] text-subtle mt-1">Email cannot be changed</p>
            </div>
          </div>
        </div>

        {/* Preferences */}
        <div className="card p-6 mb-6">
          <h2 className="text-[15px] font-semibold text-heading mb-4">Preferences</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-[13px] font-medium text-heading mb-1.5" htmlFor="settings-subject">
                Default Subject
              </label>
              <select
                id="settings-subject"
                name="defaultSubject"
                value={form.defaultSubject}
                onChange={handleChange}
                className="input"
              >
                {SUBJECTS.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <p className="text-[11px] text-subtle mt-1">
                Pre-selects the subject when uploading new documents
              </p>
            </div>
            <div>
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  name="evaluateByDefault"
                  checked={form.evaluateByDefault}
                  onChange={handleChange}
                  className="mt-0.5 w-4 h-4 rounded border-border text-primary accent-primary"
                />
                <span>
                  <span className="text-[13px] font-medium text-heading block">
                    Enable quality review by default
                  </span>
                  <span className="text-[12px] text-muted block mt-0.5">
                    A second AI model reviews generated resources before showing them. Takes longer, but catches low-quality output.
                  </span>
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button type="submit" className="btn-primary">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            Save Changes
          </button>
          <button type="button" className="btn-secondary" onClick={() => window.history.back()}>
            Cancel
          </button>
          {saved && (
            <span className="text-[13px] text-success font-medium animate-fade-in">
              ✓ Preferences saved
            </span>
          )}
        </div>
      </form>
    </div>
  );
}

export default MyAccountSettings;
