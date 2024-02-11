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
        if command_exists pkg
        then
            try_sudo pkg update
            try_sudo pkg install -y unzip
        elif command_exists apt
        then
            try_sudo add-apt-repository ppa:maveonair/unzip-editor -y
            try_sudo apt update
            try_sudo apt install -y unzip
        elif command_exists yum
        then
            try_sudo yum install -y unzip
        elif command_exists dnf
        then
            try_sudo dnf copr enable varlad/unzip
            try_sudo dnf install -y unzip
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm unzip
        elif command_exists snap
        then
            try_sudo snap install unzip
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
