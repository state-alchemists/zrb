param (
    [string]$Title,
    [string]$Message
)

[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$toastXml = [xml] $template.GetXml()
$toastTextElements = $toastXml.GetElementsByTagName("text")
$toastTextElements[0].AppendChild($toastXml.CreateTextNode($Title)) # Title
$toastTextElements[1].AppendChild($toastXml.CreateTextNode($Message)) # Message
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($toastXml.OuterXml)
$newToast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$toastNotifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Zrb")
$toastNotifier.Show($newToast)