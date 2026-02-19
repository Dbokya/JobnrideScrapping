# Load emails from text file
$emails = Get-Content "linkedin_email_campaign\useraddfile.txt"
Write-Host "Loaded $($emails.Count) emails from useraddfile.txt"

# Create Excel COM object
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
    # Open the workbook
    $wb = $excel.Workbooks.Open("$PWD\linkedin_email_campaign\users.xlsx")
    $ws = $wb.Worksheets.Item(1)
    
    $existingRows = $ws.UsedRange.Rows.Count
    Write-Host "Existing rows in Excel: $existingRows"
    
    # Insert rows at the top
    if ($existingRows -gt 0) {
        $range = $ws.Range("1:$($emails.Count)")
        $range.Insert([Microsoft.Office.Interop.Excel.XlInsertShiftDirection]::xlShiftDown) | Out-Null
    }
    
    # Add emails to the top rows
    for ($i = 0; $i -lt $emails.Count; $i++) {
        $ws.Cells.Item($i + 1, 1) = $emails[$i]
    }
    
    # Save and close
    $wb.Save()
    $wb.Close()
    
    Write-Host "Successfully added $($emails.Count) emails to the top of users.xlsx"
    Write-Host "Total rows now: $($existingRows + $emails.Count)"
}
catch {
    Write-Host "Error: $_"
}
finally {
    $excel.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
    Remove-Variable excel
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
