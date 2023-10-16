set -e

# Determine OS type
OS_TYPE=$(uname)

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

if [ ! -f "./awscliv2.zip" ]
then
    echo "Download AWS CLI"
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
else
    echo "AWS CLI already downloaded"
fi

if command_exists unzip
then
    echo "unzip is already installed."
else
    echo "Installing unzip..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install unzip
        else
            echo "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists apt
        then
            sudo apt install xclip
            sudo add-apt-repository ppa:maveonair/unzip-editor -y
            sudo apt update
            sudo apt install -y unzip
        elif command_exists yum
        then
            sudo yum install -y unzip
        elif command_exists dnf
        then
            sudo dnf copr enable varlad/unzip
            sudo dnf install -y unzip
        elif command_exists pacman
        then
            sudo pacman -Syu --noconfirm unzip
        elif command_exists snap
        then
            sudo snap install unzip
        else
            echo "No known package manager found. Please install unzip manually."
            exit 1
        fi
    else
        echo "Unsupported OS type. Please install unzip manually."
        exit 1
    fi
fi

echo "Unzip AWS CLI"
unzip awscliv2.zip
echo "Install AWS CLI"
sudo ./aws/install --update
