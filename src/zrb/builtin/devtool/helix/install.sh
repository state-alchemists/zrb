# Install helix
if command_exists hx
then
    echo "helix is already installed."
else
    echo "Installing helix..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install helix
        else
            echo "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists pkg
        then
             try_sudo pkg update
             try_sudo pkg install -y xclip helix
        elif command_exists apt
        then
             try_sudo add-apt-repository ppa:maveonair/helix-editor -y
             try_sudo apt update
             try_sudo apt install -y helix xclip
        elif command_exists yum
        then
             try_sudo yum install -y helix
        elif command_exists dnf
        then
             try_sudo dnf copr enable varlad/helix
             try_sudo dnf install -y helix
        elif command_exists pacman
        then
             try_sudo pacman -Syu --noconfirm helix
        elif command_exists snap
        then
             try_sudo snap install helix
        else
            echo "No known package manager found. Please install helix manually."
            exit 1
        fi
    else
        echo "Unsupported OS type. Please install helix manually."
        exit 1
    fi
fi

if command_exists hx
then
    hx --grammar fetch
    hx --grammar build
elif command_exists helix
then
    helix --grammar fetch
    helix --grammar build
fi
