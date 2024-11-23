# Using Google Calendar API with a Service Account

This guide explains how to set up and use a **service account** to access the Google Calendar API without requiring a user consent screen.

## Steps to Set Up a Service Account

### 1. Create a Service Account

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com).
2. Select your project or create a new one.
3. Go to **APIs & Services** > **Enabled APIs & services**.
4. Enable **Google Calendar API**.
5. Go to **APIs & Services** > **Credentials**.
6. Click on **Create Credentials** and choose **Service Account**.
7. Provide a name for the service account, then click **Create**.

### 2. Assign Roles to the Service Account

1. After creating the service account, assign it the Editor role.

### 3. Generate a Private Key

1. In the service account details, navigate to the **Keys** section.
2. Click on **Add Key** > **Create new key**.
3. Choose the **JSON** key type and click **Create**.
4. A JSON file containing the private key will be downloaded. **Store this file securely**, as it contains sensitive information.

### 4. Share the Calendar with the Service Account

1. Open Google Calendar and share the specific calendar with the service account's email address (found in the JSON key file).
2. Assign appropriate permission **"Make changes to events"** to the service account.

### 5. Set the reminders manually

Using the API, we can't set the reminders for other users (unless we have other type of permissions).
