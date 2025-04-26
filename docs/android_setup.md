🔖 [Documentation Home](../README.md) > Setting Up Zrb on Android with Termux and Proot
# Setting Up Zrb on Android with Termux and Proot

This guide explains how to install and run Zrb on an Android device using Termux and Proot. This allows you to use Zrb's powerful task automation capabilities directly on your phone.

## Prerequisites

*   An Android device.
*   Internet connection.

## Step 1: Install Termux

Termux is a terminal emulator and Linux environment app for Android.

1.  **Install Termux:**
    *   It's highly recommended to install Termux from [F-Droid](https://f-droid.org/en/packages/com.termux/). The version on the Google Play Store is outdated and no longer maintained.
    *   Download and install the F-Droid client from their website.
    *   Open F-Droid, search for "Termux", and install it.
2.  **Update Packages:**
    Open Termux and run the following commands to update the package lists and upgrade installed packages:
    ```bash
    pkg update
    pkg upgrade
    ```

## Step 2: Install Proot and a Linux Distribution

Proot allows you to run programs with a different root directory, effectively creating a lightweight containerized Linux environment within Termux. We'll install Ubuntu as an example.

1.  **Install Proot:**
    ```bash
    pkg install proot proot-distro
    ```
2.  **Install a Linux Distribution (e.g., Ubuntu):**
    ```bash
    proot-distro install ubuntu
    ```
    This command downloads and sets up an Ubuntu environment. You can choose other distributions supported by `proot-distro` if you prefer.
3.  **Login to the Linux Distribution:**
    ```bash
    proot-distro login ubuntu
    ```
    You are now inside the Ubuntu environment running within Termux. Your prompt should change, indicating you're in the proot environment.

## Step 3: Install Python and Pip (inside Proot)

Zrb requires Python. Let's install it within the Ubuntu environment.

1.  **Update Package Lists (inside Ubuntu):**
    ```bash
    apt update
    ```
2.  **Install Python and Pip:**
    ```bash
    apt install python3 python3-pip python3-venv -y
    ```
3.  **Verify Installation:**
    ```bash
    python3 --version
    pip3 --version
    ```

## Step 4: Install Zrb (inside Proot)

Now you can install Zrb using pip.

1.  **Install Zrb:**
    ```bash
    pip3 install zrb
    ```
2.  **Verify Installation:**
    ```bash
    zrb --version
    ```
    This should display the installed Zrb version.

## Step 5: Using Zrb

You can now use Zrb commands within the proot Ubuntu environment just like you would on a regular Linux system.

1.  **Navigate to your project directory:**
    Termux storage is typically mounted within the proot environment. You might need to navigate to `/data/data/com.termux/files/home/storage/shared` or similar paths to access your phone's storage, or clone your project directly within the proot environment using `git`.
2.  **Initialize Zrb (if needed):**
    If your project doesn't have a `zrb_init.py` file, you can create one.
3.  **Run Zrb tasks:**
    ```bash
    zrb your-task-name
    ```

## Exiting

*   To exit the proot Ubuntu environment, simply type `exit`.
*   To exit Termux, type `exit` again or close the app.

You have successfully set up Zrb on your Android device! You can now leverage its automation features on the go.