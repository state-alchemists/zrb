set -e
if command_exists ssh
then
    echo "SSH is already installed."
else
    echo "Installing SSH..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install openssh
        else
            echo "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists apt
        then
            sudo apt update
            sudo apt install -y openssh-client
        elif command_exists yum
        then
            sudo yum install -y openssh-clients
        elif command_exists dnf
        then
            sudo dnf install -y openssh-clients
        elif command_exists pacman
        then
            sudo pacman -Syu --noconfirm openssh
        else
            echo "No known package manager found. Please install SSH manually."
            exit 1
        fi
    else
        echo "Unsupported OS type. Please install SSH manually."
        exit 1
    fi
fi

if command_exists sshpass
then
    echo "SSHPass is already installed."
else
    echo "Installing SSHPass..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install https://raw.githubusercontent.com/kadwanev/bigboybrew/master/Library/Formula/sshpass.rb
        else
            echo "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists apt
        then
            sudo apt update
            sudo apt install -y sshpass
        elif command_exists yum
        then
            sudo yum install -y sshpass
        elif command_exists dnf
        then
            sudo dnf install -y sshpass
        elif command_exists pacman
        then
            sudo pacman -Syu --noconfirm sshpass
        else
            echo "No known package manager found. Please install SSHPass manually."
            exit 1
        fi
    else
        echo "Unsupported OS type. Please install SSHPass manually."
        exit 1
    fi
fi